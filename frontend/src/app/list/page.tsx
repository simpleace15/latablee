"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Recipe, type ShoppingList } from "@/lib/api";
import { drainOutbox, enqueue, isOnline, outboxCount } from "@/lib/outbox";
import { Button, Card, EmptyState, Input, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CheckCircle2, Circle, ListChecks, Plus, ShoppingBasket, Trash2 } from "lucide-react";

/** 1.5 -> "1½", 0.5 -> "½", 2 -> "2" — grocery-aisle readable. */
function prettyQty(q: number | null | undefined): string {
  if (q == null) return "";
  const whole = Math.floor(q);
  const frac = q - whole;
  const fracMap: [number, string][] = [[0.25, "¼"], [1 / 3, "⅓"], [0.5, "½"], [2 / 3, "⅔"], [0.75, "¾"]];
  const f = fracMap.find(([v]) => Math.abs(frac - v) < 0.02)?.[1] ?? "";
  return f ? (whole ? `${whole}${f}` : f) : String(Math.round(q * 100) / 100);
}

export default function ListPage() {
  const [loading, setLoading] = useState(true);
  const [lists, setLists] = useState<ShoppingList[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [newItem, setNewItem] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<{ listId: number; itemId: number; name: string } | null>(null);
  const [queued, setQueued] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [res, recs] = await Promise.all([api.lists(), api.recipes()]);
      setLists(res);
      setRecipes(recs);
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

  // Drain queued check-offs when we come back online (page load, tab focus, or the
  // browser's online event fires). Fresh data loads right after the queue empties.
  useEffect(() => {
    let cancelled = false;
    async function tryDrain() {
      if (!isOnline() || outboxCount() === 0) return;
      const { failed } = await drainOutbox(api);
      if (cancelled) return;
      setQueued(outboxCount());
      if (failed === 0) void load();
    }
    void tryDrain();
    window.addEventListener("online", tryDrain);
    window.addEventListener("focus", tryDrain);
    return () => {
      cancelled = true;
      window.removeEventListener("online", tryDrain);
      window.removeEventListener("focus", tryDrain);
    };
  }, [load]);

  async function addItem(e: React.FormEvent) {
    e.preventDefault();
    const lst = lists[0];
    if (!lst || !newItem.trim()) return;
    setBusy(true);
    if (!isOnline()) {
      enqueue({ kind: "add", listId: lst.id, name: newItem.trim() });
      setNewItem("");
      setQueued(outboxCount());
      setBusy(false);
      return;
    }
    try {
      await api.addListItem(lst.id, newItem.trim());
      setNewItem("");
      await load();
    } catch (err) {
      if (err instanceof Error && (err.message.includes("fetch") || err.message.includes("Failed"))) {
        enqueue({ kind: "add", listId: lst.id, name: newItem.trim() });
        setNewItem("");
        setQueued(outboxCount());
      } else {
        setError(err instanceof Error ? err.message : "Couldn't add");
      }
    } finally {
      setBusy(false);
    }
  }

  async function toggle(listId: number, itemId: number, done: boolean) {
    // optimistic flip first — the aisle can't wait on a network round-trip
    setLists((cur) =>
      cur.map((l) =>
        l.id === listId
          ? { ...l, items: l.items.map((i) => (i.id === itemId ? { ...i, done } : i)) }
          : l,
      ),
    );
    if (!isOnline()) {
      enqueue({ kind: "check", listId, itemId, done });
      setQueued(outboxCount());
      return;
    }
    try {
      await api.checkListItem(listId, itemId, done);
    } catch {
      // network blip mid-request: keep the optimistic state, queue for retry
      enqueue({ kind: "check", listId, itemId, done });
      setQueued(outboxCount());
    }
  }

  async function removeItem() {
    const t = pendingDelete;
    if (!t) return;
    await api.removeListItem(t.listId, t.itemId);
    setPendingDelete(null);
    await load();
  }

  async function genFromPlan() {
    const lst = lists[0];
    if (!lst) return;
    setBusy(true);
    try {
      await api.generateFromPlan(lst.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't generate");
    } finally {
      setBusy(false);
    }
  }

  function recipeNames(item: { from_recipe_ids: number[] }): string {
    return (item.from_recipe_ids || [])
      .map((id) => recipes.find((r) => r.id === id)?.title)
      .filter(Boolean)
      .join(" · ");
  }

  const lst = lists[0] ?? null;
  const openItems = lst?.items.filter((i) => !i.done) ?? [];
  const doneItems = lst?.items.filter((i) => i.done) ?? [];

  if (loading && lists.length === 0) return <AppLayout><Spinner /></AppLayout>;

  return (
    <AppLayout>
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl">Shopping list</h1>
        {lst && (
          <Button onClick={genFromPlan} disabled={busy}>
            <ListChecks size={18} aria-hidden /> From plan
          </Button>
        )}
      </header>

      {error && <p className="mb-3 text-sm font-semibold" style={{ color: "var(--color-destructive)" }}>{error}</p>}
      {queued > 0 && (
        <p className="mb-3 rounded-[12px] px-3 py-2 text-sm font-semibold" style={{ background: "var(--color-muted)", color: "var(--color-muted-foreground)" }}>
          {queued} change{queued === 1 ? "" : "s"} saved offline — will sync automatically when you're back online.
        </p>
      )}

      {!lst ? (
        <EmptyState
          icon={<ShoppingBasket size={40} />}
          title="No list yet."
          action={
            <Button
              onClick={async () => {
                await api.createList();
                await load();
              }}
            >
              <Plus size={18} aria-hidden /> Make a list
            </Button>
          }
        />
      ) : (
        <>
          <form onSubmit={addItem} className="mb-4 flex gap-2">
            <input
              className="flex-1 rounded-[var(--radius-control)] border px-3.5 py-2.5"
              placeholder="Add an item…"
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              style={{ borderColor: "var(--color-border)", background: "var(--color-card)", color: "var(--color-foreground)" }}
              aria-label="New item"
            />
            <Button type="submit" disabled={busy || !newItem.trim()}>
              <Plus size={18} aria-hidden /> Add
            </Button>
</form>
          <div className="flex flex-col gap-2">
            {openItems.map((item) => (
              <Card key={item.id} className="flex items-center gap-3 p-3.5">
                <button
                  className="pressable rounded-full p-1"
                  onClick={() => toggle(lst.id, item.id, true)}
                  aria-label={`Check off ${item.name}`}
                  style={{ color: "var(--color-accent)" }}
                >
                  <Circle size={22} aria-hidden />
                </button>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base">{item.name}</p>
                  {item.from_recipe_ids?.length > 0 && (
                    <p className="truncate text-xs" style={{ color: "var(--color-muted-foreground)" }}>
                      for {recipeNames(item)}
                    </p>
                  )}
                </div>
                <span className="shrink-0 text-sm font-semibold" style={{ color: "var(--color-muted-foreground)" }}>
                  {prettyQty(item.quantity)} {item.unit ?? ""}
                </span>
                <button className="pressable rounded-full p-1.5" onClick={() => setPendingDelete({ listId: lst.id, itemId: item.id, name: item.name })}
                  aria-label={`Remove ${item.name}`} style={{ color: "var(--color-muted-foreground)" }}>
                  <Trash2 size={16} aria-hidden />
                </button>
              </Card>
            ))}

            {doneItems.length > 0 && (
              <>
                <p className="mt-3 px-1 text-sm font-bold uppercase tracking-wide" style={{ color: "var(--color-muted-foreground)" }}>
                  Done · {doneItems.length}
                </p>
                {doneItems.map((item) => (
                  <Card key={item.id} className="done-row flex items-center gap-3 p-3" >
                    <button className="pressable rounded-full p-1" onClick={() => toggle(lst.id, item.id, false)}
                      aria-label={`Uncheck ${item.name}`} style={{ color: "var(--color-accent)" }}>
                      <CheckCircle2 size={22} aria-hidden />
                    </button>
                    <span className="item-name struck flex-1 truncate text-base">
                      {item.name}
                      {item.from_recipe_ids?.length > 0 && (
                        <span className="ml-2 text-xs" style={{ color: "var(--color-muted-foreground)" }}>
                          ({recipeNames(item)})
                        </span>
                      )}
                    </span>
                    <button className="pressable rounded-full p-1.5" onClick={() => setPendingDelete({ listId: lst.id, itemId: item.id, name: item.name })}
                      aria-label={`Remove ${item.name}`} style={{ color: "var(--color-muted-foreground)" }}>
                      <Trash2 size={16} aria-hidden />
                    </button>
                  </Card>
                ))}
              </>
            )}

            {lst.items.length === 0 && (
              <EmptyState icon={<ListChecks size={36} />} title="Empty list — add items by hand or fill it from your plan." />
            )}
          </div>
        </>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Remove this item?"
        detail={pendingDelete?.name}
        onConfirm={removeItem}
        onCancel={() => setPendingDelete(null)}
      />
    </AppLayout>
  );
}
