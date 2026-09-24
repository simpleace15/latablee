"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type PlanEntry, type ShoppingList, type User } from "@/lib/api";
import { Card, EmptyState, Spinner } from "@/components/ui";
import AppLayout from "./AppLayout";
import { CalendarDays, ListPlus, Plus, ShoppingBasket, Sun } from "lucide-react";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Late night";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function todayISO(): string {
  // local date, not UTC
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function TodayPage() {
  const [user, setUser] = useState<User | null>(null);
  const [entries, setEntries] = useState<PlanEntry[]>([]);
  const [lists, setLists] = useState<ShoppingList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [u, plan, listsRes] = await Promise.all([
        api.me(),
        api.plan(todayISO(), 1),
        api.lists(),
      ]);
      setUser(u);
      setEntries(plan.entries ?? []);
      setLists(listsRes);
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

  // Live sync: partner replanned tonight or ticked the shopping list → refresh.
  useEffect(() => {
    const onChange = () => void load();
    window.addEventListener("latablee:changed", onChange);
    return () => window.removeEventListener("latablee:changed", onChange);
  }, [load]);

  const dinner = entries.find((e) => e.slot === "dinner") ?? entries[0] ?? null;
  const activeList = lists[0] ?? null;
  const openItems = activeList?.items.filter((i) => !i.done) ?? [];
  const doneCount = activeList ? activeList.items.length - openItems.length : 0;

  if (loading) return <AppLayout><Spinner /></AppLayout>;

  return (
    <AppLayout>
      <header className="mb-5 flex items-end justify-between">
        <div>
          <p className="text-sm font-semibold" style={{ color: "var(--color-muted-foreground)" }}>
            {greeting()}
          </p>
          <h1 className="text-3xl">
            {user ? user.name : "Welcome"}
          </h1>
        </div>
        <Sun aria-hidden style={{ color: "var(--color-primary)" }} />
      </header>

      {error && (
        <p className="mb-4 text-sm font-semibold" style={{ color: "var(--color-destructive)" }}>{error}</p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* What's for dinner — the one big card (WAF) */}
      <Link href="/plan/" className="pressable block" aria-label="Open the meal plan">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <CalendarDays size={22} style={{ color: "var(--color-primary)" }} aria-hidden />
            <p className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--color-muted-foreground)" }}>
              Tonight
            </p>
          </div>
          <p className="mt-2 text-2xl leading-snug">
            {dinner
              ? dinner.title_override || dinner.recipe_title || "Planned"
              : "Nothing planned yet"}
          </p>
          <p className="mt-1 text-sm" style={{ color: "var(--color-muted-foreground)" }}>
            {dinner?.recipe_title ? "Tap to see the plan" : "Tap to plan dinner"}
          </p>
        </Card>
      </Link>

      {/* Shopping list summary */}
      <Link href="/list/" className="pressable mt-4 block lg:mt-0" aria-label="Open the shopping list">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <ShoppingBasket size={22} style={{ color: "var(--color-accent)" }} aria-hidden />
            <p className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--color-muted-foreground)" }}>
              Shopping list
            </p>
          </div>
          {activeList && activeList.items.length > 0 ? (
            <>
              <p className="mt-2 text-2xl">
                {openItems.length} to get
                {doneCount > 0 && (
                  <span className="ml-2 text-base" style={{ color: "var(--color-muted-foreground)" }}>
                    · {doneCount} done
                  </span>
                )}
              </p>
              <p className="mt-1 truncate text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                {openItems.slice(0, 3).map((i) => i.name).join(" · ") || "All checked off 🎉"}
              </p>
            </>
          ) : (
            <p className="mt-2 text-2xl">List is empty</p>
          )}
        </Card>
      </Link>
      </div>

      {/* Quick actions */}
      <div className="mt-6 flex gap-3">
        <Link href="/recipes/" className="pressable flex-1">
          <Card className="flex items-center justify-center gap-2 p-4">
            <Plus size={18} aria-hidden /> Recipes
          </Card>
        </Link>
        <Link href="/list/" className="pressable flex-1">
          <Card className="flex items-center justify-center gap-2 p-5">
            <ListPlus size={18} aria-hidden /> List
          </Card>
        </Link>
      </div>

      {lists.length === 0 && (
        <EmptyState
          icon={<ShoppingBasket size={40} />}
          title="No shopping list yet — make one from your plan."
        />
      )}
    </AppLayout>
  );
}