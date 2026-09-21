// Offline outbox — queues grocery check-offs made without connectivity and syncs on reconnect.
// DESIGN: check-off must never block or fail in the aisle. We flip the checkbox optimistically,
// stash the op in localStorage, and drain the queue whenever online again. Order matters
// (last action wins), so ops replay sequentially in the order made.

import { api } from "./api";

const OUTBOX_KEY = "latablee_outbox_v1";

export interface OutboxOp {
  id: string; // uuid-ish, for dedup + UI
  ts: number; // created at, for ordering/debug
  kind: "check" | "add" | "remove";
  listId: number;
  itemId?: number; // for check/remove
  done?: boolean; // for check
  name?: string; // for add
  quantity?: number | null;
  unit?: string | null;
}

function read(): OutboxOp[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(OUTBOX_KEY) || "[]") as OutboxOp[];
  } catch {
    return [];
  }
}

function write(ops: OutboxOp[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(OUTBOX_KEY, JSON.stringify(ops));
}

export function outboxCount(): number {
  return read().length;
}

export function enqueue(op: Omit<OutboxOp, "id" | "ts">) {
  const ops = read();
  ops.push({ ...op, id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, ts: Date.now() });
  write(ops);
}

export function clearOutbox() {
  write([]);
}

/** True when the browser reports connectivity (or can't tell — assume yes). */
export function isOnline(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine !== false;
}

/**
 * Drain the outbox: replay each queued op against the real API, in order.
 * Returns {sent, failed} — failed ops stay queued for a later retry.
 * The caller passes the exact api functions to avoid an import cycle.
 */
export async function drainOutbox(
  api: {
    checkListItem: (listId: number, itemId: number, done: boolean) => Promise<unknown>;
    addListItem: (listId: number, name: string, quantity?: number | null, unit?: string | null) => Promise<unknown>;
    removeListItem: (listId: number, itemId: number) => Promise<unknown>;
  },
): Promise<{ sent: number; failed: number }> {
  const ops = read();
  if (ops.length === 0) return { sent: 0, failed: 0 };
  const remaining: OutboxOp[] = [];
  let sent = 0;
  let failed = 0;
  for (const op of ops) {
    try {
      if (op.kind === "check" && op.itemId !== undefined) {
        await api.checkListItem(op.listId, op.itemId, op.done === true);
      } else if (op.kind === "add") {
        await api.addListItem(op.listId, op.name || "", op.quantity ?? null, op.unit ?? null);
      } else if (op.kind === "remove" && op.itemId !== undefined) {
        await api.removeListItem(op.listId, op.itemId);
      }
      sent += 1;
    } catch {
      failed += 1;
      remaining.push(op);
    }
  }
  write(remaining);
  return { sent, failed };
}

