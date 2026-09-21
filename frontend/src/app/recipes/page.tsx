"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type Recipe } from "@/lib/api";
import { Button, Card, Chip, EmptyState, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { ChefHat, Plus, Search } from "lucide-react";

export default function RecipesPage() {
  const [loading, setLoading] = useState(true);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [q, setQ] = useState("");
  const [activeTag, setActiveTag] = useState("");
  const [error, setError] = useState("");

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

  const allTags = Array.from(new Set(recipes.flatMap((r) => r.tags))).sort();

  return (
    <AppLayout>
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl">Recipes</h1>
        <Link href="/recipes/new/" className="pressable">
          <Button>
            <Plus size={18} aria-hidden /> Add
          </Button>
        </Link>
      </header>

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
          {recipes.map((r) => (
            <Link key={r.id} href={`/recipes/view/?id=${r.id}`} className="pressable block">
              <Card className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-heading text-lg">{r.title}</p>
                  <p className="mt-0.5 truncate text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                    {r.total_minutes ? `${r.total_minutes} min · ` : ""}
                    {r.tags.slice(0, 3).join(", ")}
                  </p>
                </div>
                {r.image_path && (
                  <img src={r.image_path} alt="" className="h-14 w-14 shrink-0 rounded-[12px] object-cover" />
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "var(--color-destructive)" }}>{error}</p>}
    </AppLayout>
  );
}