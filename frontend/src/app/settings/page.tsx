"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type Household, type User } from "@/lib/api";
import { Button, Card, Input, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { Bot, CalendarDays, Database, Download, KeyRound, Link2, LogOut, Moon, PackageOpen, RotateCcw, Sun, Trash2, Users } from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const TIMEZONES = [
  "America/Denver", "America/Chicago", "America/New_York", "America/Los_Angeles",
  "America/Phoenix", "UTC", "Europe/London", "Europe/Paris", "Australia/Sydney",
];

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [household, setHousehold] = useState<Household | null>(null);
  const [loading, setLoading] = useState(true);
  const [theme, setThemeState] = useState<string>("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState("");
  const [migFile, setMigFile] = useState<File | null>(null);
  const [migPreview, setMigPreview] = useState<{ would_import: number; skipped: number; format: string; with_images: number } | null>(null);
  const [migBusy, setMigBusy] = useState(false);
  const [migMsg, setMigMsg] = useState("");
  const restoreInputRef = useRef<HTMLInputElement | null>(null);

  // llm settings
  const [prefsDraft, setPrefsDraft] = useState<{ allergies: string; dislikes: string }>({ allergies: "", dislikes: "" });
  const [rulesDraft, setRulesDraft] = useState("");
  const [tokens, setTokens] = useState<{ id: number; name: string; created_at: string; last_used_at: string | null; revoked: boolean }[]>([]);
  const [newTokenName, setNewTokenName] = useState("");
  const [newTokenRaw, setNewTokenRaw] = useState("");
  const [tokenMsg, setTokenMsg] = useState("");
  const [icsToken, setIcsToken] = useState("");
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const [restoreMsg, setRestoreMsg] = useState("");
  const [restoreBusy, setRestoreBusy] = useState(false);
  const [prefsSaved, setPrefsSaved] = useState(false);
  const [llm, setLlm] = useState({ base_url: "", api_key: "", model: "", vision_model: "", system_prompt: "" });
  const [llmKeySet, setLlmKeySet] = useState(false);
  const [llmSaved, setLlmSaved] = useState(false);
  // admin diagnostics
  const [llmTest, setLlmTest] = useState<{ ok: boolean; seconds?: number; reply?: string; error?: string } | null>(null);
  const [llmTestBusy, setLlmTestBusy] = useState(false);
  const [llmLog, setLlmLog] = useState<Awaited<ReturnType<typeof api.adminLlmLog>>["entries"]>([]);
  const [showLog, setShowLog] = useState(false);
  const [llmTimeout, setLlmTimeout] = useState<string>("");

  useEffect(() => {
    setThemeState(window.localStorage.getItem("latablee_theme") ?? "");
    (async () => {
      try {
        const [u, h] = await Promise.all([api.me(), api.household()]);
        setUser(u);
        setHousehold(h);
      setPrefsDraft({
        allergies: (h.allergies ?? []).join(", "),
        dislikes: (h.dislikes ?? []).join(", "),
      });
      setRulesDraft((h.planning_rules ?? []).join("\n"));
      api.tokens().then((res) => setTokens(res.tokens)).catch(() => {});
        if (u.role === "admin") {
          try {
            const s = await api.llmSettings();
            try {
              const t = await api.adminLlmGetTimeout();
              setLlmTimeout(t.timeout_seconds != null ? String(t.timeout_seconds) : "");
              const lg = await api.adminLlmLog();
              setLlmLog(lg.entries);
            } catch { /* non-admin or older backend */ }
            setLlm((prev) => ({ ...prev, base_url: s.base_url, model: s.model, vision_model: s.vision_model, system_prompt: s.system_prompt ?? "" }));
            setLlmKeySet(s.api_key_set);
          } catch {
            /* not admin or not configured yet */
          }
        }
      } catch {
        /* auth gate handles redirect */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function setTheme(next: string) {
    setThemeState(next);
    if (next) window.localStorage.setItem("latablee_theme", next);
    else window.localStorage.removeItem("latablee_theme");
    if (next) document.documentElement.dataset.theme = next;
    else delete document.documentElement.dataset.theme;
  }

  async function migPreviewRun() {
    setMigMsg("");
    if (!migFile) return;
    setMigBusy(true);
    try {
      setMigPreview(await api.migratePreview(migFile));
    } catch (err) {
      setMigMsg(err instanceof Error ? err.message : "Couldn't read that file");
      setMigPreview(null);
    } finally {
      setMigBusy(false);
    }
  }

  async function migRun() {
    if (!migFile) return;
    setMigBusy(true);
    try {
      const res = await api.migrateRun(migFile);
      const fails = res.failed.length ? ` (${res.failed.length} failed: ${res.failed.slice(0, 2).map((f) => f.title).join(", ")}…)` : "";
      setMigMsg(`Imported ${res.imported} recipe${res.imported === 1 ? "" : "s"}${fails}.`);
      setMigPreview(null);
      setMigFile(null);
    } catch (err) {
      setMigMsg(err instanceof Error ? err.message : "Import failed");
    } finally {
      setMigBusy(false);
    }
  }

  async function savePrefs() {
    const parse = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);
    try {
      await api.updateHousehold({
        name: household?.name ?? "",
        allergies: parse(prefsDraft.allergies),
        dislikes: parse(prefsDraft.dislikes),
        planning_rules: rulesDraft.split("\n").map((x) => x.trim()).filter(Boolean),
      });
      setPrefsSaved(true);
      setTimeout(() => setPrefsSaved(false), 2000);
    } catch (err) {
      setSeedMsg(err instanceof Error ? err.message : "Couldn't save preferences");
    }
  }

  async function mintToken() {
    if (!newTokenName.trim()) { setTokenMsg("Give the token a name first"); return; }
    try {
      const res = await api.createToken(newTokenName.trim());
      setNewTokenRaw(res.token);
      setNewTokenName("");
      setTokenMsg("");
      api.tokens().then((res) => setTokens(res.tokens)).catch(() => {});
    } catch (err) {
      setTokenMsg(err instanceof Error ? err.message : "Couldn't create token");
    }
  }

  async function revokeToken(id: number) {
    try {
      await api.revokeToken(id);
      api.tokens().then((res) => setTokens(res.tokens)).catch(() => {});
    } catch {
      setTokenMsg("Couldn't revoke");
    }
  }

  async function doRestore() {
    if (!restoreFile) return;
    setConfirmRestore(false);
    setRestoreBusy(true);
    setRestoreMsg("");
    try {
      const res = await api.restoreBackup(restoreFile);
      const c = res.restored;
      setRestoreMsg(`Restored ${c.recipes ?? 0} recipes, ${c.plan ?? 0} planned meals, ${c.lists ?? 0} lists. Reloading…`);
      setTimeout(() => window.location.reload(), 1800);
    } catch (err) {
      setRestoreMsg(err instanceof Error ? err.message : "Restore failed — is that a LaTablée backup?");
    } finally {
      setRestoreBusy(false);
      setRestoreFile(null);
    }
  }

  async function signOut() {
    await import("@/lib/api").then((m) => m.setToken(null));
    router.replace("/login/");
  }

  async function seedDemo() {
    setSeedMsg("");
    setSeeding(true);
    try {
      const res = await api.seedDemo();
      setSeedMsg(res.seeded
        ? `Demo loaded: ${res.recipes} recipes, sample week, groceries. Demo login: ${res.admin_user} / latablee-demo`
        : res.reason || "Nothing seeded");
    } catch (err) {
      setSeedMsg(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setSeeding(false);
    }
  }

  async function makeInvite() {
    setInviteError("");
    try {
      const res = await api.createInvite();
      setInviteUrl(res.invite_url);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Couldn't create invite");
    }
  }

  async function saveLLM() {
    setLlmSaved(false);
    try {
      await api.saveLLMSettings({
        base_url: llm.base_url,
        api_key: llm.api_key || "",
        model: llm.model || "gpt-4o-mini",
        vision_model: llm.vision_model || "",
        system_prompt: llm.system_prompt,
      });
      setLlmSaved(true);
      setTimeout(() => setLlmSaved(false), 2500);
    } catch {
      /* surfaced by button state */
    }
  }

  async function runLlmTest() {
    setLlmTestBusy(true);
    setLlmTest(null);
    try {
      setLlmTest(await api.adminLlmTest());
      const lg = await api.adminLlmLog();
      setLlmLog(lg.entries);
    } catch (err) {
      setLlmTest({ ok: false, error: err instanceof Error ? err.message : "Test failed" });
    } finally {
      setLlmTestBusy(false);
    }
  }

  async function saveLlmTimeout() {
    const n = Number(llmTimeout);
    if (!Number.isFinite(n) || n < 5) return;
    try {
      await api.adminLlmSetTimeout(n);
      const lg = await api.adminLlmLog();
      setLlmLog(lg.entries);
    } catch {
      /* keep prior state */
    }
  }

  async function downloadExport() {
    const token = window.localStorage.getItem("latablee_token");
    const res = await fetch("/api/v1/export/download-json", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "latablee-export.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (loading) return <AppLayout><Spinner /></AppLayout>;

  return (
    <AppLayout>
      <h1 className="mb-4 text-2xl">Settings</h1>

      {/* Household */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <Users size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Household</h2>
        </div>
        {household ? (
          <div className="flex flex-col gap-3">
            <Input label="Name" value={household.name} onChange={(e) => setHousehold({ ...household, name: e.target.value })} />
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold">Timezone</span>
              <select
                value={household.timezone}
                onChange={(e) => setHousehold({ ...household, timezone: e.target.value })}
                className="w-full rounded-[var(--radius-control)] border px-3.5 py-2.5"
                style={{ borderColor: "var(--color-border)", background: "var(--color-background)", color: "var(--color-foreground)" }}
              >
                {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </label>
            <Button
              onClick={async () => {
                await api.updateHousehold({
                  name: household.name,
                  timezone: household.timezone,
                  allergies: household.allergies,
                  dislikes: household.dislikes,
                  favorites: household.favorites,
                  things_to_remember: household.things_to_remember,
                });
              }}
            >
              Save
            </Button>
          </div>
        ) : (
          <p className="text-base" style={{ color: "var(--color-muted-foreground)" }}>Not onboarded yet.</p>
        )}
      </Card>

      {/* Invite */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <Link2 size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Invite your people</h2>
        </div>
        {user?.role === "admin" ? (
          <>
            <Button onClick={makeInvite}>Create invite link</Button>
            {inviteError && <p className="mt-2 text-sm" style={{ color: "var(--color-destructive)" }}>{inviteError}</p>}
            {inviteUrl && (
              <p className="mt-3 break-all rounded-[12px] px-3 py-2.5 text-sm" style={{ background: "var(--color-muted)" }}>
                {inviteUrl}
              </p>
            )}
          </>
        ) : (
          <p className="text-base" style={{ color: "var(--color-muted-foreground)" }}>
            Ask your household admin for an invite link.
          </p>
        )}
      </Card>

      {/* Demo data (admin only) */}
      {user?.role === "admin" && (
        <Card className="mb-4 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Database size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
            <h2 className="font-heading text-lg">Demo data</h2>
          </div>
          <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            Loads ~12 sample recipes, a sample week plan, and a grocery list. Only works on an
            empty instance — existing data is never touched.
          </p>
          <Button variant="ghost" onClick={seedDemo} disabled={seeding}>
            {seeding ? "Loading…" : "Load demo data"}
          </Button>
          {seedMsg && (
            <p className="mt-3 break-words rounded-[12px] px-3 py-2.5 text-sm" style={{ background: "var(--color-muted)" }}>
              {seedMsg}
            </p>
          )}
        </Card>
      )}

      {/* Migration import (admin only) */}
      {user?.role === "admin" && (
        <Card className="mb-4 p-5">
          <div className="mb-3 flex items-center gap-2">
            <PackageOpen size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
            <h2 className="font-heading text-lg">Import from Mealie or other apps</h2>
          </div>
          <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            Bring your existing collection: upload a Mealie backup zip (Settings → Backups →
            Create Backup in Mealie), a zip of recipe JSON files, or a single recipe JSON.
            Recipes, photos, tags, and source links all come across. Nothing is saved until
            you confirm the preview.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="file" accept=".zip,.json"
              onChange={(e) => { setMigFile(e.target.files?.[0] ?? null); setMigPreview(null); setMigMsg(""); }}
              className="text-sm"
              style={{ color: "var(--color-foreground)" }}
            />
            <Button onClick={migPreviewRun} disabled={!migFile || migBusy}>
              {migBusy ? "Reading…" : "Preview"}
            </Button>
          </div>
          {migPreview && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-[12px] px-3 py-2.5 text-sm" style={{ background: "var(--color-muted)" }}>
              <span>
                Found <b>{migPreview.would_import}</b> recipe{migPreview.would_import === 1 ? "" : "s"}
                {migPreview.with_images > 0 && <> with <b>{migPreview.with_images}</b> photo{migPreview.with_images === 1 ? "" : "s"}</>}
                {migPreview.skipped > 0 && <>, {migPreview.skipped} skipped</>} — format: {migPreview.format}
              </span>
              <Button onClick={migRun} disabled={migBusy}>{migBusy ? "Importing…" : "Import now"}</Button>
            </div>
          )}
          {migMsg && <p className="mt-3 break-words text-sm" style={{ color: "var(--color-foreground)" }}>{migMsg}</p>}
        </Card>
      )}

      {/* AI endpoint */}
      {user?.role === "admin" && (
        <Card className="mb-4 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Bot size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
            <h2 className="font-heading text-lg">AI endpoint</h2>
          </div>
          <div className="flex flex-col gap-3">
            <Input label="Base URL (OpenAI-compatible)" value={llm.base_url} onChange={(e) => setLlm({ ...llm, base_url: e.target.value })}
              placeholder="http://your-llm-host:8080/v1" />
            <Input label={llmKeySet ? "API key (saved — leave blank to keep)" : "API key (optional)"} type="password"
              value={llm.api_key} onChange={(e) => setLlm({ ...llm, api_key: e.target.value })} />
            <Input label="Model" value={llm.model} onChange={(e) => setLlm({ ...llm, model: e.target.value })} />
            <Input label="Vision model (for photo import)" value={llm.vision_model} onChange={(e) => setLlm({ ...llm, vision_model: e.target.value })} />
            <div>
              <span className="mb-1.5 block text-sm font-semibold">Custom AI instructions</span>
              <textarea
                className="w-full rounded-[12px] px-3 py-2 text-base min-h-[96px]"
                style={{ background: "var(--color-muted)", color: "var(--color-foreground)", border: "1px solid var(--color-border)" }}
                value={llm.system_prompt}
                onChange={(e) => setLlm({ ...llm, system_prompt: e.target.value })}
                placeholder="Extra instructions for every AI reply — e.g. Always prefer budget-friendly meals. Suggest leftovers night on Fridays."
                aria-label="Custom AI instructions"
              />
              <p className="mt-1 text-xs" style={{ color: "var(--color-muted-foreground)" }}>
                Appended to every AI call — meal planning, suggestions, photo import, voice.
              </p>
            </div>
            <Input
              label="AI timeout — seconds (default 120; raise it if your model is slow or cold-loading)"
              value={llmTimeout}
              onChange={(e) => setLlmTimeout(e.target.value)}
              placeholder="120"
              inputMode="numeric"
            />
            <div className="flex gap-2">
              <Button className="flex-1" onClick={saveLLM}>{llmSaved ? "Saved ✓" : "Save AI settings"}</Button>
              <Button className="flex-1" variant="accent" onClick={saveLlmTimeout} disabled={!llmTimeout}>Save timeout</Button>
            </div>
            <Button variant="ghost" onClick={runLlmTest} disabled={llmTestBusy}>
              {llmTestBusy ? "Testing…" : "Test connection"}
            </Button>
            {llmTest && (
              <p className="text-sm" style={{ color: llmTest.ok ? "var(--color-success, #4caf7d)" : "var(--color-danger, #d65a4a)" }}>
                {llmTest.ok
                  ? `✓ AI answered in ${llmTest.seconds}s — "${llmTest.reply}"`
                  : `✗ ${llmTest.error}`}
              </p>
            )}

            <div className="border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
              <button className="text-sm underline" style={{ color: "var(--color-muted-foreground)" }}
                onClick={() => setShowLog(!showLog)}>
                {showLog ? "Hide" : "Show"} recent AI activity ({llmLog.length})
              </button>
              {showLog && (
                <div className="mt-3 max-h-72 overflow-y-auto rounded-[var(--radius-card)] border p-3" style={{ borderColor: "var(--color-border)" }}>
                  {llmLog.length === 0 ? (
                    <p className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                      No AI calls yet — photo import, refill-my-week, and voice all show up here.
                    </p>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {llmLog.map((e, i) => (
                        <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                          <span style={{ color: e.status === "ok" ? "var(--color-success, #4caf7d)" : "var(--color-danger, #d65a4a)" }}>
                            {e.status === "ok" ? "✓" : "✗"}
                          </span>
                          <span className="font-mono text-xs" style={{ color: "var(--color-muted-foreground)" }}>{e.at}</span>
                          <span>{e.kind}{e.image ? " +photo" : ""} · {e.model}</span>
                          {e.seconds != null && <span style={{ color: "var(--color-muted-foreground)" }}>{e.seconds}s</span>}
                          {e.prompt_chars != null && <span style={{ color: "var(--color-muted-foreground)" }}>{e.prompt_chars} chars</span>}
                          {e.error && <span style={{ color: "var(--color-danger, #d65a4a)" }}>{e.error}</span>}
                          {e.note && <span style={{ color: "var(--color-muted-foreground)" }}>{e.note}</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Food preferences */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <Users size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Food preferences</h2>
        </div>
        <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
          The AI avoids these in suggestions and meal planning. Comma-separated.
        </p>
        <div className="flex flex-col gap-3">
          <Input
            label="Never these (allergies & hard nos)"
            value={prefsDraft.allergies}
            onChange={(e) => setPrefsDraft({ ...prefsDraft, allergies: e.target.value })}
            placeholder="shellfish, cilantro"
          />
          <Input
            label="Dislikes (avoid when possible)"
            value={prefsDraft.dislikes}
            onChange={(e) => setPrefsDraft({ ...prefsDraft, dislikes: e.target.value })}
            placeholder="mushrooms, olives"
          />
        </div>
        <p className="mt-4 mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
          Planning rules — free-text instructions the meal planner follows. One per line.
        </p>
        <textarea
          className="w-full rounded-[12px] px-3 py-2 text-base min-h-[88px]"
          style={{ background: "var(--color-muted)", color: "var(--color-foreground)", border: "1px solid var(--color-border)" }}
          value={rulesDraft}
          onChange={(e) => setRulesDraft(e.target.value)}
          placeholder={"Only 1 chicken meal per week\nDon\u0027t repeat any meals from the last 2 weeks\nMeatless on Wednesdays"}
          aria-label="Planning rules for the meal planner"
        />
        <div className="mt-3">
          <Button onClick={() => void savePrefs()}>{prefsSaved ? "Saved ✓" : "Save preferences"}</Button>
        </div>
      </Card>

      {/* Appearance */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <Sun size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Appearance</h2>
        </div>
        <div className="flex gap-2">
          {[
            { key: "", label: "Auto", icon: null },
            { key: "light", label: "Light", icon: Sun },
            { key: "dark", label: "Dark", icon: Moon },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className="pressable flex-1 rounded-[var(--radius-control)] border px-3 py-2.5 text-sm font-semibold"
              onClick={() => setTheme(key)}
              style={{
                borderColor: theme === key ? "var(--color-primary)" : "var(--color-border)",
                background: theme === key ? "var(--color-muted)" : "transparent",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </Card>

      {/* Device tokens (integrations) */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <KeyRound size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Device tokens</h2>
        </div>
        <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
          Long-lived keys for integrations (Home Assistant, scripts) — they don't expire
          like logins. Create one per device, revoke anytime.
        </p>
        {newTokenRaw && (
          <div className="mb-3 rounded-[12px] p-3" style={{ background: "var(--color-muted)" }}>
            <p className="mb-1 text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-muted-foreground)" }}>
              Copy it now — shown only once
            </p>
            <code className="break-all text-sm" style={{ color: "var(--color-foreground)" }}>{newTokenRaw}</code>
          </div>
        )}
        <div className="mb-2 flex gap-2">
          <Input
            label=""
            value={newTokenName}
            onChange={(e) => setNewTokenName(e.target.value)}
            placeholder="e.g. Home Assistant"
          />
          <Button onClick={() => void mintToken()}>Create token</Button>
        </div>
        {tokenMsg && <p className="mb-2 text-sm" style={{ color: "var(--color-destructive)" }}>{tokenMsg}</p>}
        {tokens.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {tokens.map((t) => (
              <div key={t.id} className="flex items-center justify-between gap-2 rounded-[12px] px-3 py-2"
                   style={{ background: "var(--color-muted)" }}>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold" style={{ color: t.revoked ? "var(--color-muted-foreground)" : "var(--color-foreground)" }}>
                    {t.name}{t.revoked ? " · revoked" : ""}
                  </p>
                  <p className="text-xs" style={{ color: "var(--color-muted-foreground)" }}>
                    {t.last_used_at ? `last used ${new Date(t.last_used_at).toLocaleDateString()}` : "never used"}
                  </p>
                </div>
                {!t.revoked && (
                  <Button variant="ghost" onClick={() => void revokeToken(t.id)}>
                    <Trash2 size={14} aria-hidden /> Revoke
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
      {/* Calendar feed */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <CalendarDays size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Calendar feed</h2>
        </div>
        <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
          Subscribe your meal plan from any calendar app (iPhone, Google Calendar,
          Home Assistant). Paste one of your device tokens — the feed is read-only.
        </p>
        <Input
          label=""
          value={icsToken}
          onChange={(e) => setIcsToken(e.target.value)}
          placeholder="Paste a device token (lat_…)"
        />
        {icsToken.startsWith("lat_") && (
          <div className="mt-2 rounded-[12px] p-3" style={{ background: "var(--color-muted)" }}>
            <code className="break-all text-sm" style={{ color: "var(--color-foreground)" }}>
              {`${window.location.origin}/api/v1/calendar?token=${icsToken}`}
            </code>
          </div>
        )}
      </Card>

      {/* Restore backup (admin) */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <RotateCcw size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Restore from backup</h2>
        </div>
        <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
          Upload a backup archive (.zip) or JSON export. <b style={{ color: "var(--color-foreground)" }}>
          This replaces everything</b> with the backup's contents — logins come back too.
        </p>
        <input
          type="file"
          accept=".zip,.json"
          className="hidden"
          onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)}
          ref={(el) => { restoreInputRef.current = el; }}
        />
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => restoreInputRef.current?.click()} disabled={restoreBusy}>
            {restoreFile ? restoreFile.name : "Choose backup file…"}
          </Button>
          <Button onClick={() => setConfirmRestore(true)} disabled={!restoreFile || restoreBusy}>
            {restoreBusy ? "Restoring…" : "Restore"}
          </Button>
        </div>
        {restoreMsg && (
          <p className="mt-2 text-sm" style={{ color: "var(--color-foreground)" }}>{restoreMsg}</p>
        )}
      </Card>

      {/* Data */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <Download size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Your data</h2>
        </div>
        <Button onClick={downloadExport}>
          <Download size={16} aria-hidden /> Download JSON export
        </Button>
      </Card>

      <ConfirmDialog
        open={confirmRestore}
        title="Restore this backup?"
        detail={`Everything currently in LaTablée will be replaced by ${restoreFile?.name ?? "the backup"}. This can't be undone.`}
        confirmLabel="Replace everything"
        onConfirm={() => void doRestore()}
        onCancel={() => setConfirmRestore(false)}
      />

      {/* Account */}
      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <LogOut size={18} aria-hidden style={{ color: "var(--color-primary)" }} />
          <h2 className="font-heading text-lg">Account</h2>
        </div>
        <p className="mb-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
          Signed in as <b style={{ color: "var(--color-foreground)" }}>{user?.name}</b>
          {user?.role === "admin" && <> · admin</>}
        </p>
        <Button variant="ghost" onClick={signOut}>
          <LogOut size={16} aria-hidden /> Sign out
        </Button>
      </Card>
    </AppLayout>
  );
}