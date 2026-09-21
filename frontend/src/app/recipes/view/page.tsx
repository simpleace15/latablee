"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type Recipe } from "@/lib/api";
import { Button, Card, Spinner } from "@/components/ui";
import AppLayout from "../../AppLayout";
import { ArrowLeft, ChefHat, Clock, ImagePlus, Trash2 } from "lucide-react";

function RecipeDetailView() {
  const router = useRouter();
  const search = useSearchParams();
  const id = Number(search.get("id"));
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cookMode, setCookMode] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [servings, setServings] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.recipe(id);
      setRecipe(r);
      setServings(r.servings);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not found");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (Number.isFinite(id) && id > 0) void load();
    else {
      setError("Invalid recipe");
      setLoading(false);
    }
  }, [id]);

  async function remove() {
    if (!recipe?.id) return;
    await api.deleteRecipe(recipe.id);
    router.push("/recipes/");
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    const res = await api.uploadRecipeImage(id, file);
    setRecipe((r) => (r ? { ...r, image_path: res.image_path } : r));
  }

  function scale(qty: number | null | undefined): string {
    if (qty == null || !recipe) return "";
    const scaled = (qty / recipe.servings) * servings;
    return Number.isInteger(scaled) ? String(scaled) : scaled.toFixed(2).replace(/\.00$/, "");
  }

  if (loading) return <AppLayout><Spinner /></AppLayout>;
  if (error || !recipe) {
    return (
      <AppLayout>
        <p className="pt-10 text-center" style={{ color: "var(--color-muted-foreground)" }}>{error || "Not found"}</p>
      </AppLayout>
    );
  }

  // Cook mode: full-screen, big steps, tap to advance
  if (cookMode) {
    return (
      <main className="min-h-dvh" style={{ background: "var(--color-background)" }}>
        <header className="flex items-center justify-between px-4 pt-4">
          <button className="pressable rounded-full p-2" onClick={() => setCookMode(false)} aria-label="Exit cook mode">
            <ArrowLeft size={22} aria-hidden />
          </button>
          <p className="font-heading text-lg">{recipe.title}</p>
          <span className="w-9" />
        </header>

        <div className="flex flex-col items-center gap-6 px-6 pb-10 pt-8">
          <p className="text-center text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            Step {activeStep + 1} of {recipe.instructions.length}
          </p>

          {recipe.instructions[activeStep] ? (
            <p
              className="mx-auto max-w-xl text-center"
              style={{
                fontSize: "22px",
                lineHeight: 1.5,
                fontWeight: 600,
              }}
            >
              {recipe.instructions[activeStep]}
            </p>
          ) : (
            <p className="text-lg" style={{ color: "var(--color-muted-foreground)" }}>
              All done — enjoy!
            </p>
          )}

          <div className="mt-auto flex w-full max-w-md flex-col gap-3 px-6 pb-10">
            <div className="flex gap-2">
              {recipe.instructions.map((_, i) => (
                <div
                  key={i}
                  className="h-1.5 flex-1 rounded-full"
                  style={{ background: i <= activeStep ? "var(--color-primary)" : "var(--color-muted)" }}
                />
              ))}
            </div>
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setActiveStep(Math.max(0, activeStep - 1))} disabled={activeStep === 0}>
                Back
              </Button>
              <Button
                className="flex-1"
                size="lg"
                variant={activeStep >= recipe.instructions.length - 1 ? "accent" : "primary"}
                onClick={() =>
                  activeStep >= recipe.instructions.length - 1
                    ? setCookMode(false)
                    : setActiveStep(activeStep + 1)
                }
              >
                {activeStep >= recipe.instructions.length - 1 ? "Done" : "Next step"}
              </Button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <AppLayout>
      <div className="mb-3 flex items-center gap-2">
        <Link href="/recipes/" className="pressable rounded-full p-1.5" aria-label="Back to recipes">
          <ArrowLeft size={20} aria-hidden />
        </Link>
        <p className="text-sm font-semibold" style={{ color: "var(--color-muted-foreground)" }}>Recipe</p>
      </div>

      {recipe.image_path && (
        <img
          src={recipe.image_path}
          alt={recipe.title}
          className="mb-4 h-44 w-full rounded-[var(--radius-card)] object-cover"
        />
      )}

      <div className="mb-2 flex items-start justify-between gap-3">
        <h1 className="text-3xl">{recipe.title}</h1>
        <button className="pressable rounded-full p-2" onClick={() => fileRef.current?.click()} aria-label="Change photo">
          <ImagePlus size={18} aria-hidden />
        </button>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onUpload} />
      </div>

      {recipe.description && (
        <p className="mb-4 text-base" style={{ color: "var(--color-muted-foreground)" }}>{recipe.description}</p>
      )}

      <div className="mb-5 flex flex-wrap items-center gap-3 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
        {recipe.total_minutes && <span className="flex items-center gap-1"><Clock size={14} aria-hidden /> {recipe.total_minutes} min</span>}
        <span>Serves <b>{servings}</b></span>
        {recipe.source_name && <span>via {recipe.source_name}</span>}
      </div>

      <h2 className="mb-2 font-heading text-xl">Ingredients</h2>
      <Card className="mb-5 p-4">
        <ul className="flex flex-col gap-2.5">
          {recipe.ingredients.map((ing, i) => (
            <li key={i} className="flex items-baseline justify-between gap-3 text-base">
              <span>{ing.name}</span>
              <span className="shrink-0 font-semibold" style={{ color: "var(--color-muted-foreground)" }}>
                {scale(ing.quantity)} {ing.unit}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-heading text-xl">Steps</h2>
        <Button onClick={() => setCookMode(true)}>
          <ChefHat size={16} aria-hidden /> Cook mode
        </Button>
      </div>
      <div className="flex flex-col gap-2.5">
        {recipe.instructions.map((step, i) => (
          <Card key={i} className="p-4">
            <p className="text-base leading-relaxed">
              <span className="mr-2 font-heading font-bold" style={{ color: "var(--color-primary)" }}>{i + 1}.</span>
              {step}
            </p>
          </Card>
        ))}
      </div>

      <div className="mt-8 flex justify-center">
        <Button variant="danger" onClick={remove}>
          <Trash2 size={16} aria-hidden /> Delete recipe
        </Button>
      </div>
    </AppLayout>
  );
}

export default function RecipeDetailPage() {
  return (
    <Suspense fallback={null}>
      <RecipeDetailView />
    </Suspense>
  );
}
