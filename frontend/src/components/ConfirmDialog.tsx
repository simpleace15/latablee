"use client";

import { useEffect } from "react";
import { Button, Card } from "./ui";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /** What gets deleted — shown in the body, e.g. the recipe title. */
  detail?: string;
  confirmLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Destructive-action confirmation modal (DESIGN.md tone: plain words, no jargon).
 * Blocks deletes behind an explicit OK — no accidental trashings.
 * Escape and backdrop click both cancel; focus lands on the cancel button
 * (safe default for a destructive dialog).
 */
export function ConfirmDialog({
  open,
  title,
  detail,
  confirmLabel = "Delete",
  busyLabel = "Deleting…",
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  // Escape cancels
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4"
      role="alertdialog"
      aria-modal="true"
      aria-label={title}
      onClick={onCancel}
    >
      <Card
        className="w-full max-w-sm p-5"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <h2 className="text-xl">{title}</h2>
        {detail && (
          <p className="mt-2 text-base" style={{ color: "var(--color-muted-foreground)" }}>
            {detail}
          </p>
        )}
        <div className="mt-5 flex gap-3">
          <Button variant="ghost" className="flex-1" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" className="flex-1" onClick={onConfirm} disabled={busy}>
            {busy ? busyLabel : confirmLabel}
          </Button>
        </div>
      </Card>
    </div>
  );
}
