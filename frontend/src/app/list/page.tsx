"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type ShoppingList } from "@/lib/api";
import { Button, Card, EmptyState, Input, Spinner } from "@/components/ui";
import AppLayout from "../AppLayout";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CheckCircle2, Circle, ListChecks, Plus, ShoppingBasket, Trash2 } from "lucide-react";

export default function ListPage() {
  const [loading, setLoading] = useState(true);
  const [lists, setLists] = useState<ShoppingList[]>([]);
  const [newItem, setNewItem] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<{ listId: number; itemId: number; name: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.lists();
      setLists(res);
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

  async function addItem(e: React.FormEvent) {
    e.preventDefault();
    const lst = lists[0];
    if (!lst || !newItem.trim()) return;
    setBusy(true);
    try {
      await api.addListItem(lst.id, newItem.trim());
      setNewItem("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(listId: number, itemId: number, done: boolean) {
    await api.checkListItem(listId, itemId, done);
    await load();
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
                <p className="min-w-0 flex-1 truncate text-base">{item.name}</p>
                <span className="text-sm" style={{ color: "var(--color-muted-foreground)" }}>
                  {item.quantity ?? ""} {item.unit ?? ""}
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
                    <span className="item-name struck flex-1 truncate text-base">{item.name}</span>
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
