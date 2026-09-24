# Reel/video recipe import ("Recime"-style, self-hosted): paste a TikTok/Instagram/YouTube
# URL -> yt-dlp grabs the video + platform captions (fast path) -> faster-whisper
# transcribes locally when captions are missing -> PyAV samples frames so on-screen
# ingredient text reaches the vision LLM -> structured recipe draft for review.
#
# Everything runs inside the container: no cloud services, no subscriptions.
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.services.llm_client import chat

PROMPT = (
    "You are extracting a recipe from a social-media cooking video (a reel). You get the "
    "spoken transcript (if any) and sampled video frames — the frames often show on-screen "
    "text: ingredient lists, measurements, steps. Combine BOTH sources: spoken details fill "
    "what the frames lack and vice versa. Return ONLY a JSON object: title (string), "
    "description (string), servings (int), prep_minutes (int|null), cook_minutes (int|null), "
    "ingredients (list of {name, quantity (number|null), unit (string|null)}), instructions "
    "(ordered list of step strings). If the video is NOT a recipe, return "
    '{"error": "not_a_recipe"} instead. Transcribe faithfully — quantities come from what '
    "is said or shown, never invented."
)

# Whisper model: small enough for CPU (~75 MB), strong on short spoken recipes.
WHISPER_MODEL = os.environ.get("LATABLEE_WHISPER_MODEL", "small.en")
MAX_FRAMES = 6  # sampled across the video for the vision call
FRAME_HEIGHT = 512  # downscale frames — enough for on-screen text, cheap tokens

_URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?(?:tiktok\.com|instagram\.com|youtube\.com|youtu\.be|"
    r"facebook\.com|pinterest\.com|x\.com|twitter\.com)/\S+",
    re.I,
)


def extract_url(text: str) -> str | None:
    m = _URL_RE.search(text)
    return m.group(0) if m else None


_log = logging.getLogger("latablee.reel")


class _YdlQuiet:
    """yt-dlp logger shim: swallow info/progress chatter, keep warnings/errors."""

    def debug(self, msg: str) -> None:  # noqa: ARG002
        pass

    def warning(self, msg: str) -> None:
        _log.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        _log.error("yt-dlp: %s", msg)


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def _probe_duration(path: str) -> float:
    out = subprocess.run(  # noqa: S603 — fixed binary name, tempdir-controlled path
        [  # noqa: S607 — ffprobe by name
         "ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _download(url: str, tmp: Path, progress: Callable[[str, str], None] | None = None) -> dict:
    """yt-dlp: video file + platform captions when available. Raises RuntimeError on failure."""
    import yt_dlp

    video = tmp / "video"
    opts = {
        "outtmpl": str(video) + ".%(ext)s",
        "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/bv*/b",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt/srv3/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _YdlQuiet(),
        # IG/TikTok sometimes need a browserUA; keep default headers first
        "http_headers": {"User-Agent": "Mozilla/5.0 (compatible; LaTablee/1.0)"},
        "socket_timeout": 30,
        "retries": 2,
    }
    if progress:
        def hook(d: dict) -> None:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes")
                pct = f" {round(100 * done / total)}%" if total and done else ""
                progress("downloading", pct)
        opts["progress_hooks"] = [hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    # outtmpl is video.<ext> and subs land as video.<lang>.vtt — exclude subs/parts and
    # prefer the biggest media file (video+audio mux > audio-only fallback).
    media = [f for f in tmp.glob("video.*")
             if f.suffix not in {".vtt", ".part", ".jpg"} and f.is_file()]
    if not media:
        raise RuntimeError("Download produced no video file")
    media.sort(key=lambda f: f.stat().st_size, reverse=True)
    subs = sorted(tmp.glob("video*.vtt"))
    return {"path": str(media[0]), "info": info, "subs": subs}


def _vtt_to_text(vtt_path: Path) -> str:
    """Strip VTT markup -> plain transcript text."""
    lines: list[str] = []
    seen: set[str] = set()
    for raw in vtt_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if "-->" in line or re.fullmatch(r"\d+", line):
            continue
        text = re.sub(r"<[^>]+>", "", line).strip()
        if text and text not in seen:  # rolling captions repeat lines
            seen.add(text)
            lines.append(text)
    return " ".join(lines)


def _transcribe(audio_path: str) -> str:
    """Local whisper transcription; no network, CPU-only."""
    from faster_whisper import WhisperModel

    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments if seg.text.strip())


def _extract_audio(video_path: str, tmp: Path) -> str | None:
    out = str(tmp / "audio.m4a")
    r = subprocess.run(  # noqa: S603 — fixed binary name, tempdir-controlled path
        ["ffmpeg", "-y", "-i", video_path,  # noqa: S607 — ffmpeg by name
         "-vn", "-acodec", "copy", out],
        capture_output=True, timeout=120,
    )
    if r.returncode != 0 or not os.path.exists(out):
        # some containers lack native m4a muxing; force re-encode to wav
        r = subprocess.run(  # noqa: S603 — fixed binary name, tempdir-controlled path
            ["ffmpeg", "-y", "-i", video_path,  # noqa: S607 — ffmpeg by name
             "-vn", "-ar", "16000", "-ac", "1", out],
            capture_output=True, timeout=120,
        )
    return out if r.returncode == 0 and os.path.exists(out) else None


def _sample_frames(video_path: str, tmp: Path) -> list[str]:
    """PyAV: decode MAX_FRAMES evenly spaced frames -> base64 JPEGs (downscaled)."""
    import av

    duration = _probe_duration(video_path)
    container = av.open(video_path)
    stream = container.streams.video[0]
    tb = float(stream.time_base) if stream.time_base is not None else 0.0
    total = float(stream.duration * tb) if (stream.duration and duration <= 0) else duration
    if total <= 0:
        container.close()
        return []
    step = total / (MAX_FRAMES + 1)
    targets = [step * (i + 1) for i in range(MAX_FRAMES)]
    frames: list[str] = []
    want = iter(sorted(targets))
    next_t = next(want, None)
    for frame in container.decode(stream):
        ts = float(frame.pts * tb) if frame.pts is not None else 0.0
        if next_t is None:
            break
        if ts >= next_t:
            img = frame.to_image()
            w, h = img.size
            if h > FRAME_HEIGHT:
                img = img.resize((int(w * FRAME_HEIGHT / h), FRAME_HEIGHT))
            buf = tmp / f"frame{len(frames)}.jpg"
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            frames.append(base64.b64encode(buf.read_bytes()).decode())
            next_t = next(want, None)
    container.close()
    return frames


def import_from_reel(
    url: str, progress: Callable[[str, str], None] | None = None
) -> dict[str, Any]:
    """Full pipeline: download -> captions/whisper -> frames -> vision LLM -> draft.
    progress(stage, detail) is called as each stage starts (for the job store)."""
    with tempfile.TemporaryDirectory(prefix="latablee-reel-") as td:
        tmp = Path(td)
        dl = _download(url, tmp)
        transcript = ""
        for sub in dl["subs"]:
            transcript = _vtt_to_text(sub)
            if transcript:
                break
        if transcript:
            if progress:
                progress("transcribing", "using platform captions")
        else:
            if progress:
                progress("transcribing", "listening to the video (local whisper)")
            audio = _extract_audio(dl["path"], tmp)
            if audio:
                transcript = _transcribe(audio)
        if progress:
            progress("reading frames", "")
        frames = _sample_frames(dl["path"], tmp)
        if not transcript and not frames:
            raise RuntimeError("No transcript or frames could be extracted from this URL")

        parts = []
        if transcript:
            parts.append(f"SPOKEN TRANSCRIPT:\n{transcript}")
        if frames:
            parts.append("VIDEO FRAMES (sampled through the video):")
        prompt = PROMPT + "\n\n" + "\n\n".join(parts)

        if progress:
            progress("thinking", "reading transcript + frames")
        b64_list = frames or None
        text = chat(prompt, json_mode=True, image_b64=b64_list)
        try:
            draft = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"AI returned invalid JSON: {text[:200]}") from exc
        if isinstance(draft, dict) and draft.get("error"):
            raise ValueError(str(draft["error"]))
        draft.setdefault("source_url", url)
        platform = dl["info"].get("extractor_key", "").split(":")[0].capitalize() if dl["info"] else "Video"
        creator = dl["info"].get("uploader") or dl["info"].get("channel")
        draft.setdefault("source_name", f"{platform} — {creator}" if creator else platform)
        return draft
