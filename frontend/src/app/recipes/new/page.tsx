"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Ingredient, type Recipe } from "@/lib/api";
import { Button, Card, Input, Spinner } from "@/components/ui";
import AppLayout from "../../AppLayout";
import { Camera, Globe, Keyboard, Sparkles } from "lucide-react";

type Tab = "manual" | "url" | "photo" | "ai";

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
  const [aiPrompt, setAiPrompt] = useState("");
  const [parsed, setParsed] = useState<Partial<Recipe> | null>(null);
  const [busy, setBusy] = useState(false);
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
    setDraft({ ...emptyRecipe(), ...p });
    setStepsText((p.instructions ?? []).join("\n"));
    setParsed(null);
    setTab("manual");
  }

  const tabs: { key: Tab; label: string; icon: typeof Keyboard }[] = [
    { key: "manual", label: "Type it", icon: Keyboard },
    { key: "url", label: "From link", icon: Globe },
    { key: "photo", label: "Photo", icon: Camera },
    { key: "ai", label: "AI", icon: Sparkles },
  ];

  return (
    <AppLayout>
      <h1 className="mb-4 text-2xl">Add a recipe</h1>

      <div className="mb-5 grid grid-cols-4 gap-2">
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