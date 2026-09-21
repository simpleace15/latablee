"use client";

import { useEffect, useState } from "react";
import { api, type Household, type User } from "@/lib/api";
import { Button, Card, Input, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { Bot, Database, Download, Link2, Moon, Sun, Users } from "lucide-react";

const TIMEZONES = [
  "America/Denver", "America/Chicago", "America/New_York", "America/Los_Angeles",
  "America/Phoenix", "UTC", "Europe/London", "Europe/Paris", "Australia/Sydney",
];

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [household, setHousehold] = useState<Household | null>(null);
  const [loading, setLoading] = useState(true);
  const [theme, setThemeState] = useState<string>("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState("");

  // llm settings
  const [llm, setLlm] = useState({ base_url: "", api_key: "", model: "", vision_model: "" });
  const [llmKeySet, setLlmKeySet] = useState(false);
  const [llmSaved, setLlmSaved] = useState(false);

  useEffect(() => {
    setThemeState(window.localStorage.getItem("latablee_theme") ?? "");
    (async () => {
      try {
        const [u, h] = await Promise.all([api.me(), api.household()]);
        setUser(u);
        setHousehold(h);
        if (u.role === "admin") {
          try {
            const s = await api.llmSettings();
            setLlm((prev) => ({ ...prev, base_url: s.base_url, model: s.model, vision_model: s.vision_model }));
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
      });
      setLlmSaved(true);
      setTimeout(() => setLlmSaved(false), 2500);
    } catch {
      /* surfaced by button state */
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
            <Button onClick={saveLLM}>{llmSaved ? "Saved ✓" : "Save AI settings"}</Button>
          </div>
        </Card>
      )}

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
    </AppLayout>
  );
}