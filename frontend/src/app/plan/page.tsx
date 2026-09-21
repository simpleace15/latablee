"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type PlanEntry, type Recipe } from "@/lib/api";
import { Button, Card, Chip, EmptyState, Input, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CalendarDays, Plus, Sparkles, Trash2 } from "lucide-react";

interface Proposal {
  date: string;
  slot: string;
  from_book: boolean;
  title: string;
  why: string;
  recipe: Partial<Recipe> | null;
}

const SLOTS = ["breakfast", "lunch", "dinner", "other"] as const;
type Slot = (typeof SLOTS)[number];

const SLOT_LABEL: Record<Slot, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  other: "Other",
};

function fmtDay(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function PlanPage() {
  const [loading, setLoading] = useState(true);
  const [entries, setEntries] = useState<PlanEntry[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [weekStart, setWeekStart] = useState<string>("");

  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickDate, setPickDate] = useState(todayISO());
  const [pickSlot, setPickSlot] = useState<Slot>("dinner");
  const [pickRecipeId, setPickRecipeId] = useState<number | null>(null);
  const [pickTitle, setPickTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<{ id: number; label: string } | null>(null);
  const [refilling, setRefilling] = useState(false);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [refillMsg, setRefillMsg] = useState("");
  const [savingIdx, setSavingIdx] = useState<number | null>(null);

  const load = useCallback(async (start?: string) => {
    setLoading(true);
    try {
      const [plan, recipesRes] = await Promise.all([api.plan(start, 7), api.recipes()]);
      setEntries(plan.entries ?? []);
      setRecipes(recipesRes);
      setWeekStart(plan.start);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addEntry() {
    setBusy(true);
    try {
      if (!pickRecipeId && !pickTitle.trim()) {
        throw new Error("Pick a recipe or type a title");
      }
      await api.addPlanEntry({
        date: pickDate,
        slot: pickSlot,
        recipe_id: pickRecipeId,
        title_override: pickRecipeId ? null : pickTitle.trim(),
      });
      setPickerOpen(false);
      setPickRecipeId(null);
      setPickTitle("");
      await load(weekStart);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  }

  async function refillWeek() {
    setRefilling(true);
    setProposals([]);
    setRefillMsg("");
    try {
      const res = await api.refillWeek({ days: 7, slots: ["dinner"] });
      if (res.message) {
        setRefillMsg(res.message);
      } else {
        const parts: string[] = [];
        if (res.filled.length) parts.push(`Planned ${res.filled.length} from your book`);
        if (res.proposals.length) parts.push(`${res.proposals.length} new idea${res.proposals.length === 1 ? "" : "s"} below`);
        setRefillMsg(parts.join(" · ") || "Nothing to add");
        setProposals(res.proposals);
      }
      await load(weekStart);
    } catch (err) {
      setRefillMsg(err instanceof Error ? err.message : "Refill failed");
    } finally {
      setRefilling(false);
    }
  }

  async function saveProposal(p: Proposal, idx: number) {
    if (!p.recipe) return;
    setSavingIdx(idx);
    try {
      await api.saveProposal({ recipe: p.recipe, date: p.date, slot: p.slot });
      setProposals((cur) => cur.filter((_, i) => i !== idx));
      setRefillMsg(`"${p.title}" saved to your book and planned`);
      await load(weekStart);
    } catch (err) {
      setRefillMsg(err instanceof Error ? err.message : "Couldn't save");
    } finally {
      setSavingIdx(null);
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    await api.deletePlanEntry(pendingDelete.id);
    setPendingDelete(null);
    await load(weekStart);
  }

  function ymd(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function shiftWeek(delta: number) {
    const d = new Date(weekStart + "T12:00:00");
    d.setDate(d.getDate() + delta * 7);
    void load(ymd(d));
  }

  if (loading && !weekStart) return <AppLayout><Spinner /></AppLayout>;

  const days: { iso: string; entries: PlanEntry[] }[] = [];
  if (weekStart) {
    const base = new Date(weekStart + "T12:00:00");
    for (let i = 0; i < 7; i++) {
      const d = new Date(base);
      d.setDate(d.getDate() + i);
      const iso = ymd(d);
      days.push({ iso, entries: entries.filter((e) => e.date === iso) });
    }
  }

  return (
    <AppLayout>
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl">The plan</h1>
        <div className="flex gap-2">
          <Button onClick={() => void refillWeek()} disabled={refilling} variant="accent">
            <Sparkles size={18} aria-hidden /> {refilling ? "Thinking…" : "Refill week"}
          </Button>
          <Button
            onClick={() => { setPickDate(todayISO()); setPickerOpen(true); }}
          >
            <Plus size={18} aria-hidden /> Add
          </Button>
        </div>
      </header>

      {refillMsg && (
        <p className="mb-3 rounded-[12px] px-3 py-2 text-sm font-semibold"
           style={{ background: "var(--color-muted)", color: "var(--color-muted-foreground)" }}>
          {refillMsg}
        </p>
      )}

      {proposals.length > 0 && (
        <div className="mb-5 flex flex-col gap-2">
          <p className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--color-muted-foreground)" }}>
            New ideas — save the ones you want
          </p>
          {proposals.map((p, idx) => (
            <Card key={`${p.date}-${p.slot}-${idx}`} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-heading text-lg">{p.title}</p>
                  <p className="text-xs" style={{ color: "var(--color-muted-foreground)" }}>
                    {fmtDay(p.date)} · {SLOT_LABEL[p.slot as Slot] || p.slot}
                    {p.why ? ` — ${p.why}` : ""}
                  </p>
                </div>
                <Button onClick={() => void saveProposal(p, idx)} disabled={savingIdx === idx}>
                  {savingIdx === idx ? "…" : "Save to book"}
                </Button>
              </div>
              {p.recipe?.ingredients && p.recipe.ingredients.length > 0 && (
                <p className="mt-1.5 truncate text-xs" style={{ color: "var(--color-muted-foreground)" }}>
                  {p.recipe.ingredients.map((i: { name: string }) => i.name).slice(0, 6).join(", ")}
                  {p.recipe.ingredients.length > 6 ? ` +${p.recipe.ingredients.length - 6} more` : ""}
                </p>
              )}
            </Card>
          ))}
        </div>
      )}

      <div className="mb-4 flex items-center justify-between">
        <Button variant="ghost" onClick={() => shiftWeek(-1)} aria-label="Previous week">←</Button>
        <p className="text-sm font-semibold" style={{ color: "var(--color-muted-foreground)" }}>
          {weekStart
            ? `${new Date(weekStart + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ` +
              (() => {
                const d = new Date(weekStart + "T12:00:00");
                d.setDate(d.getDate() + 6);
                return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
              })()
            : ""}
        </p>
        <Button variant="ghost" onClick={() => shiftWeek(1)} aria-label="Next week">→</Button>
      </div>

      {error && <p className="mb-3 text-sm font-semibold" style={{ color: "var(--color-destructive)" }}>{error}</p>}

      <div className="grid grid-cols-1 gap-3 lg:flex lg:gap-2">
        {days.map(({ iso, entries: dayEntries }) => (
          <Card key={iso} className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="font-heading text-lg">{fmtDay(iso)}</p>
              <button
                className="pressable text-sm font-semibold"
                style={{ color: "var(--color-primary)" }}
                onClick={() => { setPickDate(iso); setPickerOpen(true); }}
              >
                + add
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {dayEntries.length === 0 && (
                <p className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>Nothing planned</p>
              )}
              {dayEntries.map((e) => (
                <div key={e.id} className="flex items-center justify-between gap-3 rounded-[12px] px-3 py-2" style={{ background: "var(--color-muted)" }}>
                  <p className="truncate text-base">
                    <span className="font-semibold capitalize">{e.slot}</span>
                    {" · "}
                    {e.title_override || e.recipe_title || "Planned"}
                  </p>
                  <button
                    className="pressable rounded-full p-2"
                    style={{ color: "var(--color-muted-foreground)" }}
                    onClick={() => setPendingDelete({ id: e.id, label: `${SLOT_LABEL[e.slot as Slot] || e.slot} — ${e.title_override || e.recipe_title || "Planned"}` })}
                    aria-label={`Remove ${e.slot} on ${iso}`}
                  >
                    <Trash2 size={16} aria-hidden />
                  </button>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      {pickerOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <Card className="w-full max-w-md p-5">
            <h2 className="text-xl">Add to the plan</h2>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Date" type="date" value={pickDate} onChange={(e) => setPickDate(e.target.value)} />
              <div>
                <span className="mb-2 block text-sm font-semibold">Meal</span>
                <div className="flex flex-wrap gap-2">
                  {SLOTS.map((s) => (
                    <Chip key={s} active={pickSlot === s} onClick={() => setPickSlot(s)}>
                      {SLOT_LABEL[s]}
                    </Chip>
                  ))}
                </div>
              </div>
              <div>
                <span className="mb-2 block text-sm font-semibold">Recipe</span>
                <div className="flex flex-col gap-2" style={{ maxHeight: "40vh", overflowY: "auto" }}>
                  <button
                    className={`pressable rounded-[12px] border px-3.5 py-2.5 text-left ${pickRecipeId === null ? "font-bold" : ""}`}
                    style={{ borderColor: pickRecipeId === null ? "var(--color-border)" : "var(--color-border)", background: pickRecipeId === null ? "var(--color-muted)" : "transparent" }}
                    onClick={() => { setPickRecipeId(null); }}
                  >
                    Just a title (no recipe)
                  </button>
                  {recipes.map((r) => (
                    <button
                      key={r.id}
                      className={`pressable rounded-[12px] border px-3.5 py-2.5 text-left ${pickRecipeId === r.id ? "font-bold" : ""}`}
                      style={{ background: pickRecipeId === r.id ? "var(--color-muted)" : "transparent" }}
                      onClick={() => { setPickRecipeId(r.id); }}
                    >
                      {r.title}
                    </button>
                  ))}
                </div>
              </div>
              {pickRecipeId === null && (
                <Input label="Title" value={pickTitle} onChange={(e) => setPickTitle(e.target.value)}
                  placeholder="Leftovers night" />
              )}
            </div>
            <div className="mt-5 flex gap-3">
              <Button variant="ghost" onClick={() => setPickerOpen(false)} className="flex-1">Cancel</Button>
              <Button className="flex-1" onClick={addEntry} disabled={busy}>{busy ? "…" : "Add"}</Button>
            </div>
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Remove from the plan?"
        detail={pendingDelete?.label}
        onConfirm={remove}
        onCancel={() => setPendingDelete(null)}
      />
    </AppLayout>
  );
}