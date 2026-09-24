"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type Recipe } from "@/lib/api";
import { Button, Card, Chip, EmptyState, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { ChefHat, Heart, Plus, Search, Sparkles } from "lucide-react";

export default function RecipesPage() {
  const [loading, setLoading] = useState(true);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [q, setQ] = useState("");
  const [activeTag, setActiveTag] = useState("");
  const [favOnly, setFavOnly] = useState(false);
  const [error, setError] = useState("");
  const [ideas, setIdeas] = useState<Array<Partial<Recipe> & { cuisine?: string; why?: string }>>([]);
  const [ideaBusy, setIdeaBusy] = useState(false);
  const [savingId, setSavingId] = useState("");

  const load = useCallback(async (query: string, tag: string) => {
    setLoading(true);
    try {
      const res = await api.recipes(query, tag);
      setRecipes(res);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load("", "");
  }, [load]);

  async function toggleFav(e: React.MouseEvent, id: number, next: boolean) {
    e.preventDefault(); // don't navigate to the recipe
    e.stopPropagation();
    setRecipes((cur) => cur.map((r) => (r.id === id ? { ...r, is_favorite: next } : r)));
    try {
      await api.toggleFavorite(id, next);
    } catch {
      setRecipes((cur) => cur.map((r) => (r.id === id ? { ...r, is_favorite: !next } : r)));
    }
  }

  const allTags = Array.from(new Set(recipes.flatMap((r) => r.tags))).sort();

  async function findIdeas() {
    setIdeaBusy(true);
    try {
      const res = await api.discoverIdeas({ count: 3 });
      setIdeas(res.ideas ?? []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't get ideas");
    } finally {
      setIdeaBusy(false);
    }
  }

  async function addToBook(i: number, idea: Partial<Recipe>) {
    setSavingId(String(i));
    try {
      await api.saveProposal({ recipe: idea });
      setIdeas((cur) => cur.filter((_, idx) => idx !== i));
      void load(q, activeTag); // the book grew — refresh
    } catch {
      /* keep card; surfaced by state reset */
    } finally {
      setSavingId("");
    }
  }

  return (
    <AppLayout>
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl">Recipes</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => void findIdeas()} disabled={ideaBusy}>
            <Sparkles size={18} aria-hidden /> {ideaBusy ? "Thinking…" : "Find something new"}
          </Button>
          <Link href="/recipes/new/" className="pressable">
            <Button>
              <Plus size={18} aria-hidden /> Add
            </Button>
          </Link>
        </div>
      </header>

      {ideaBusy && <Spinner />}
      {ideas.length > 0 && (
        <Card className="mb-4 p-4">
          <div className="mb-2 flex items-center gap-2">
            <Sparkles size={16} aria-hidden style={{ color: "var(--color-primary)" }} />
            <span className="font-heading font-semibold">New ideas for the book</span>
          </div>
          <div className="flex flex-col gap-3">
            {ideas.map((idea, i) => (
              <div key={`${idea.title}-${i}`} className="rounded-[var(--radius-card)] border p-3" style={{ borderColor: "var(--color-border)" }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{idea.title}</p>
                    <p className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                      {idea.cuisine ? `${idea.cuisine} · ` : ""}{idea.why || idea.description}
                    </p>
                  </div>
                  <Button
                    variant="accent"
                    disabled={savingId === String(i)}
                    onClick={() => void addToBook(i, idea)}
                  >
                    {savingId === String(i) ? "Adding…" : "Add to book"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
          <Button className="mt-3" variant="ghost" onClick={() => setIdeas([])}>Dismiss</Button>
        </Card>
      )}

      <div className="mb-4 flex items-center gap-2">
        <div
          className="flex flex-1 items-center gap-2 rounded-[var(--radius-control)] border px-3"
          style={{ borderColor: "var(--color-border)", background: "var(--color-card)" }}
        >
          <Search size={16} aria-hidden style={{ color: "var(--color-muted-foreground)" }} />
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              void load(e.target.value, activeTag);
            }}
            placeholder="Search recipes, ingredients, tags…"
            className="w-full bg-transparent py-2.5 outline-none"
            style={{ color: "var(--color-foreground)" }}
            aria-label="Search recipes"
          />
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <Chip active={favOnly} onClick={() => { const n = !favOnly; setFavOnly(n); void load(q, activeTag && "") }}>
          <Heart size={14} aria-hidden className="inline" /> Favorites
        </Chip>
      </div>

      {allTags.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {allTags.map((t) => (
            <Chip
              key={t}
              active={activeTag === t}
              onClick={() => {
                const next = activeTag === t ? "" : t;
                setActiveTag(next);
                void load(q, next);
              }}
            >
              {t}
            </Chip>
          ))}
        </div>
      )}

      {loading && recipes.length === 0 ? (
        <Spinner />
      ) : recipes.length === 0 ? (
        <EmptyState
          icon={<ChefHat size={40} />}
          title="No recipes yet. Add one by hand, from a link, or snap a photo of a cookbook page."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {recipes
            .filter((r) => (favOnly ? r.is_favorite : true))
            .map((r) => (
            <Link key={r.id} href={`/recipes/view/?id=${r.id}`} className="pressable block">
              <Card className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-heading text-lg">{r.title}</p>
                  <p className="mt-0.5 truncate text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                    {r.total_minutes ? `${r.total_minutes} min · ` : ""}
                    {r.tags.slice(0, 3).join(", ")}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    className="pressable rounded-full p-1.5"
                    onClick={(e) => void toggleFav(e, r.id as number, !r.is_favorite)}
                    aria-label={r.is_favorite ? `Unfavorite ${r.title}` : `Favorite ${r.title}`}
                    style={{ color: r.is_favorite ? "var(--color-destructive)" : "var(--color-muted-foreground)" }}
                  >
                    <Heart size={18} aria-hidden fill={r.is_favorite ? "currentColor" : "none"} />
                  </button>
                  {r.image_path && (
                    <img src={r.image_path} alt="" className="h-14 w-14 rounded-[12px] object-cover" />
                  )}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "var(--color-destructive)" }}>{error}</p>}
    </AppLayout>
  );
}