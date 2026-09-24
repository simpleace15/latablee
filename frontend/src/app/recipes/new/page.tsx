"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Ingredient, type Recipe } from "@/lib/api";
import { Button, Card, Input, Spinner } from "@/components/ui";
import AppLayout from "../../AppLayout";
import { Camera, Clapperboard, Globe, Keyboard, Sparkles } from "lucide-react";

type Tab = "manual" | "url" | "photo" | "reel" | "ai";

function emptyRecipe(): Partial<Recipe> {
  return {
    title: "",
    description: "",
    servings: 4,
    instructions: [],
    ingredients: [],
    tags: [],
  };
}

export default function NewRecipePage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("manual");

  // manual form
  const [draft, setDraft] = useState<Partial<Recipe>>(emptyRecipe());
  const [ingName, setIngName] = useState("");
  const [ingQty, setIngQty] = useState("");
  const [ingUnit, setIngUnit] = useState("");
  const [stepsText, setStepsText] = useState("");

  // url / photo / ai state
  const [url, setUrl] = useState("");
  const [reelUrl, setReelUrl] = useState("");
  const [aiPrompt, setAiPrompt] = useState("");
  const [parsed, setParsed] = useState<Partial<Recipe> | null>(null);
  const [busy, setBusy] = useState(false);

  // multi-URL queue: paste N links -> fetch all -> review one at a time
  type QueueItem = { url: string; ok: boolean; parsed?: Partial<Recipe>; error?: string };
  const [queueText, setQueueText] = useState("");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [queueIdx, setQueueIdx] = useState(0);
  const [queueBusy, setQueueBusy] = useState(false);
  const [queueDone, setQueueDone] = useState(false);
  const queueCurrent = queue[queueIdx];
  const queueRemaining = queue.length - queueIdx;

  async function importQueue() {
    setQueueBusy(true);
    setError("");
    try {
      const res = await api.importFromUrls(queueText);
      setQueue(res.results);
      setQueueIdx(0);
      setQueueDone(false);
      const first = res.results[0];
      setParsed(first?.ok ? { ...emptyRecipe(), ...first.parsed } : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't fetch those links");
    } finally {
      setQueueBusy(false);
    }
  }

  function queueAdvance(nextIdx: number, loadFirst = false) {
    setQueueIdx(nextIdx);
    if (nextIdx >= queue.length) {
      setQueueDone(true);
      setParsed(null);
      return;
    }
    const next = queue[nextIdx];
    if (loadFirst || next?.ok) {
      setParsed(next.ok ? { ...emptyRecipe(), ...next.parsed } : null);
    }
  }

  function queueSave() {
    // save current then auto-advance to next item
    (async () => {
      setBusy(true);
      try {
        const r = parsed as Recipe;
        if (!r.title?.trim()) throw new Error("Give it a title");
        await api.createRecipe(r);
        queueAdvance(queueIdx + 1);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't save");
      } finally {
        setBusy(false);
      }
    })();
  }

  function queueSkip() {
    queueAdvance(queueIdx + 1);
  }
  const [error, setError] = useState("");

  async function importUrl() {
    setBusy(true);
    setError("");
    try {
      const res = await api.importFromUrl(url);
      setParsed({ ...emptyRecipe(), ...res.parsed });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't parse that link");
    } finally {
      setBusy(false);
    }
  }

  async function importReel() {
    if (!reelUrl.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.importReel(reelUrl);
      setParsed({ ...emptyRecipe(), ...res.parsed });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't extract a recipe from that video");
    } finally {
      setBusy(false);
    }
  }

  async function importPhoto(file: File) {
    setBusy(true);
    setError("");
    try {
      const res = await api.importFromPhoto(file);
      setParsed({ ...emptyRecipe(), ...res.parsed });
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI couldn't read that photo");
    } finally {
      setBusy(false);
    }
  }

  async function generateAI() {
    setBusy(true);
    setError("");
    try {
      const res = await api.generateRecipe({ prompt: aiPrompt });
      setParsed({ ...emptyRecipe(), ...res.parsed });
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI didn't return a recipe");
    } finally {
      setBusy(false);
    }
  }

  function addIngredient() {
    if (!ingName.trim()) return;
    const ing: Ingredient = {
      name: ingName.trim(),
      quantity: ingQty ? Number(ingQty) : null,
      unit: ingUnit || null,
    };
    setDraft((d) => ({ ...d, ingredients: [...(d.ingredients ?? []), ing] }));
    setIngName("");
    setIngQty("");
    setIngUnit("");
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      const r = draft as Recipe;
      if (!r.title.trim()) throw new Error("Give it a title");
      const saved = await api.createRecipe(r);
      router.push(`/recipes/view/?id=${saved.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
      setBusy(false);
    }
  }

  function loadIntoForm(p: Partial<Recipe>) {
    setDraft({ ...emptyRecipe(), ...p, source_url: p.source_url ?? null, source_name: p.source_name ?? null });
    setStepsText((p.instructions ?? []).join("\n"));
    setParsed(null);
    setTab("manual");
  }

  const tabs: { key: Tab; label: string; icon: typeof Keyboard }[] = [
    { key: "manual", label: "Type it", icon: Keyboard },
    { key: "url", label: "From link", icon: Globe },
    { key: "reel", label: "Reel", icon: Clapperboard },
    { key: "photo", label: "Photo", icon: Camera },
    { key: "ai", label: "AI", icon: Sparkles },
  ];

  return (
    <AppLayout>
      <h1 className="mb-4 text-2xl">Add a recipe</h1>

      <div className="mb-5 grid grid-cols-5 gap-2">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className="pressable flex flex-col items-center gap-1.5 rounded-[var(--radius-control)] border px-2 py-3 text-xs font-semibold"
            style={{
              borderColor: tab === key ? "var(--color-primary)" : "var(--color-border)",
              background: tab === key ? "var(--color-muted)" : "transparent",
            }}
          >
            <Icon size={18} aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {error && <p className="mb-3 text-sm font-semibold" style={{ color: "var(--color-destructive)" }}>{error}</p>}

      {/* Parsed-recipe review step (URL / photo / AI all land here) */}
      {parsed ? (
        <Card className="p-5">
          <p className="text-sm font-semibold" style={{ color: "var(--color-muted-foreground)" }}>
            Looks good? Review, tweak, then save.
          </p>
          {parsed.source_url && (
            <a
              href={parsed.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold underline"
              style={{ color: "var(--color-primary)" }}
            >
              <Globe size={14} aria-hidden /> View original at {parsed.source_name || "source"}
            </a>
          )}
          <div className="mt-4 flex flex-col gap-4">
            <Input label="Title" value={parsed.title ?? ""} onChange={(e) => setParsed({ ...parsed, title: e.target.value })} />
            <Input label="Description" value={parsed.description ?? ""} onChange={(e) => setParsed({ ...parsed, description: e.target.value })} />
            <Input label="Servings" type="number" value={parsed.servings ?? 4} onChange={(e) => setParsed({ ...parsed, servings: Number(e.target.value) })} />
            <div>
              <span className="mb-1.5 block text-sm font-semibold">Ingredients</span>
              <ul className="mb-2 flex flex-col gap-1.5">
                {(parsed.ingredients ?? []).map((ing, i) => (
                  <li key={i} className="text-base" style={{ color: "var(--color-muted-foreground)" }}>
                    {ing.name} {ing.quantity != null ? `· ${ing.quantity} ${ing.unit ?? ""}` : ""}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <span className="mb-1.5 block text-sm font-semibold">Steps</span>
              <ol className="mb-2 flex list-decimal flex-col gap-1.5 pl-5">
                {(parsed.instructions ?? []).map((s, i) => (
                  <li key={i} className="text-base">{s}</li>
                ))}
              </ol>
            </div>
          </div>
          <div className="mt-5 flex gap-3">
            <Button variant="ghost" className="flex-1" onClick={() => loadIntoForm(parsed)}>Edit more</Button>
            <Button className="flex-1" onClick={() => api.createRecipe(parsed).then((r) => router.push(`/recipes/view/?id=${r.id}`))}>
              Save recipe
            </Button>
          </div>
        </Card>
      ) : tab === "manual" ? (
        <div className="flex flex-col gap-4">
          <Input label="Title" value={draft.title ?? ""} onChange={(e) => setDraft({ ...draft, title: e.target.value })} required />
          <Input label="Description (optional)" value={draft.description ?? ""} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
          <Input label="Servings" type="number" min={1} value={draft.servings ?? 4} onChange={(e) => setDraft({ ...draft, servings: Number(e.target.value) })} />

          <Card className="p-4">
            <p className="mb-3 text-sm font-bold uppercase tracking-wide" style={{ color: "var(--color-muted-foreground)" }}>
              Ingredients
            </p>
            <ul className="mb-3 flex flex-col gap-1.5">
              {(draft.ingredients ?? []).map((ing, i) => (
                <li key={i} className="flex items-center justify-between text-base">
                  <span>{ing.name}</span>
                  <span className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                    {ing.quantity ?? ""} {ing.unit ?? ""}
                    <button
                      className="pressable ml-2"
                      onClick={() => setDraft((d) => ({ ...d, ingredients: (d.ingredients ?? []).filter((_, j) => j !== i) }))}
                      aria-label={`Remove ${ing.name}`}
                      style={{ color: "var(--color-destructive)" }}
                    >
                      ✕
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input className="flex-[2] rounded-[12px] border px-3 py-2.5" placeholder="Name" value={ingName}
                onChange={(e) => setIngName(e.target.value)}
                style={{ borderColor: "var(--color-border)", background: "var(--color-background)" }} aria-label="Ingredient name" />
              <input className="flex-1 rounded-[12px] border px-3 py-2.5" placeholder="Qty" type="number" value={ingQty}
                onChange={(e) => setIngQty(e.target.value)}
                style={{ borderColor: "var(--color-border)", background: "var(--color-background)" }} aria-label="Quantity" />
              <input className="flex-1 rounded-[12px] border px-3 py-2.5" placeholder="Unit" value={ingUnit}
                onChange={(e) => setIngUnit(e.target.value)}
                style={{ borderColor: "var(--color-border)", background: "var(--color-background)" }} aria-label="Unit" />
              <Button onClick={addIngredient}>Add</Button>
            </div>
          </Card>

          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold">Steps (one per line)</span>
            <textarea
              className="w-full rounded-[var(--radius-control)] border px-3.5 py-2.5"
              rows={6}
              value={stepsText}
              onChange={(e) => {
                setStepsText(e.target.value);
                setDraft((d) => ({ ...d, instructions: e.target.value.split("\n").filter((s) => s.trim()) }));
              }}
              style={{ borderColor: "var(--color-border)", background: "var(--color-background)", color: "var(--color-foreground)" }}
            />
          </label>

          <Input label="Tags (comma-separated)" value={(draft.tags ?? []).join(", ")}
            onChange={(e) => setDraft({ ...draft, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) })} />

          <Button size="lg" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save recipe"}</Button>
        </div>
      ) : tab === "url" ? (
        <Card className="p-5">
          <Input label="Recipe link" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          <Button className="mt-4 w-full" size="lg" onClick={importUrl} disabled={busy || !url}>
            {busy ? "Reading…" : "Read the recipe"}
          </Button>
          <p className="mt-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            Works with most recipe sites. You'll review before it's saved.
          </p>

          <div className="my-5 border-t" style={{ borderColor: "var(--color-border)" }} />

          <label className="text-sm font-medium">Import a batch of links</label>
          <textarea
            className="mt-2 w-full rounded-[var(--radius-card)] border p-3 text-sm"
            style={{ borderColor: "var(--color-border)", background: "var(--color-background)", color: "var(--color-foreground)", minHeight: "5.5rem" }}
            placeholder={"Paste as many recipe links as you like — anything else in the text is ignored.\nhttps://…\nhttps://…"}
            value={queueText}
            onChange={(e) => setQueueText(e.target.value)}
          />
          <Button className="mt-3 w-full" onClick={importQueue} disabled={queueBusy || !queueText.trim()}>
            {queueBusy ? "Fetching all…" : "Fetch all & review"}
          </Button>
          <p className="mt-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            Each link is fetched one at a time and queued for review — nothing is saved until you approve it.
          </p>

          {queue.length > 0 && !queueDone && (
            <div className="mt-5 rounded-[var(--radius-card)] border p-4" style={{ borderColor: "var(--color-border)" }}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">
                  Reviewing {queueIdx + 1} of {queue.length}
                </span>
                <span style={{ color: "var(--color-muted-foreground)" }}>
                  {queue.filter((q) => q.ok).length} parsed · {queue.filter((q) => !q.ok).length} failed
                </span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--color-border)" }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${((queueIdx) / queue.length) * 100}%`, background: "var(--color-primary, #e0592a)" }} />
              </div>
              {queueCurrent && (
                <p className="mt-3 truncate text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                  {queueCurrent.ok ? "✓" : "✗"} {queueCurrent.url}
                  {queueCurrent.error ? ` — ${queueCurrent.error}` : ""}
                </p>
              )}
              <div className="mt-4 flex gap-2">
                <Button className="flex-1" size="lg" onClick={queueSave} disabled={!queueCurrent?.ok || busy}>
                  {busy ? "Saving…" : "Save & next"}
                </Button>
                <Button className="flex-1" size="lg" variant="ghost" onClick={queueSkip}>
                  Skip
                </Button>
              </div>
            </div>
          )}
          {queueDone && (
            <div className="mt-5 rounded-[var(--radius-card)] border p-4" style={{ borderColor: "var(--color-border)" }}>
              <p className="text-sm font-medium">Queue done — {queue.filter((q) => q.ok).length} of {queue.length} imported.</p>
              {queue.some((q) => !q.ok) && (
                <ul className="mt-2 space-y-1 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                  {queue.filter((q) => !q.ok).map((q) => (
                    <li key={q.url} className="truncate">✗ {q.url} — {q.error}</li>
                  ))}
                </ul>
              )}
              <Button className="mt-3" variant="ghost" onClick={() => { setQueue([]); setQueueIdx(0); setQueueDone(false); setQueueText(""); }}>
                Start another batch
              </Button>
            </div>
          )}
        </Card>
      ) : tab === "reel" ? (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <Clapperboard size={20} aria-hidden style={{ color: "var(--color-primary)" }} />
            <h2 className="font-heading text-lg">Import from a reel</h2>
          </div>
          <p className="mb-4 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            Paste a TikTok / Instagram / YouTube video link (or the whole share text).
            LaTablée downloads it, reads the spoken steps and on-screen text locally, and
            drafts the recipe — no account or subscription needed.
          </p>
          <Input
            label="Video link"
            value={reelUrl}
            onChange={(e) => setReelUrl(e.target.value)}
            placeholder="https://www.tiktok.com/@creator/video/…"
          />
          <Button className="mt-4 w-full" size="lg" onClick={() => void importReel()} disabled={busy || !reelUrl.trim()}>
            {busy ? "Watching the video…" : "Grab the recipe"}
          </Button>
        </Card>
      ) : tab === "photo" ? (
        <Card className="p-5">
          <label className="pressable flex flex-col items-center gap-3 rounded-[var(--radius-card)] border border-dashed px-6 py-10 text-center"
            style={{ borderColor: "var(--color-border)" }}>
            <Camera size={28} aria-hidden style={{ color: "var(--color-muted-foreground)" }} />
            <span className="text-base">Snap or upload a photo of the recipe</span>
            <span className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>
              AI reads the page and drafts it for review — needs an AI endpoint in Settings.
            </span>
            <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && importPhoto(e.target.files[0])} />
          </label>
        </Card>
      ) : (
        <Card className="p-5">
          <Input label="Describe what you want to make" value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
            placeholder="Weeknight chicken thighs, one pan, kid-friendly" />
          <Button className="mt-4 w-full" size="lg" onClick={generateAI} disabled={busy || !aiPrompt}>
            {busy ? "Writing…" : "Draft it"}
          </Button>
        </Card>
      )}
      {busy && tab !== "manual" && <Spinner label="Working…" />}
    </AppLayout>
  );
}