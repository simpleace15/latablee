"use client";

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "accent" | "ghost" | "danger";
  size?: "md" | "lg";
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", className = "", ...rest },
  ref,
) {
  const base = "pressable inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] font-semibold focus-visible:outline-2";
  const variants: Record<string, string> = {
    primary: "text-[var(--color-on-primary)]",
    accent: "text-[var(--color-on-accent)]",
    ghost: "text-[var(--color-foreground)]",
    destructive: "text-[var(--color-on-destructive)]",
  };
  const sizes: Record<string, string> = {
    md: "min-h-11 px-4 text-base",
    lg: "min-h-12 px-5 text-base",
  };
  const style: React.CSSProperties = {
    background:
      variant === "primary"
        ? "var(--color-primary)"
        : variant === "accent"
          ? "var(--color-accent)"
          : variant === "ghost"
            ? "transparent"
            : "var(--color-destructive)",
  };
  return (
    <button
      ref={ref}
      className={`${base} ${variants[variant] ?? variants.primary} ${sizes[size]} ${className}`}
      style={style}
      {...rest}
    />
  );
});

type CardProps = {
  children: ReactNode;
  className?: string;
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
};

export function Card({ children, className = "", onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`rounded-[var(--radius-card)] border bg-card ${className}`}
      style={{
        borderColor: "var(--color-border)",
        background: "var(--color-card)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      {children}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label?: string };

export function Input({ label, className = "", ...rest }: InputProps) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-sm font-semibold" style={{ color: "var(--color-foreground)" }}>
          {label}
        </span>
      )}
      <input
        className="w-full rounded-[var(--radius-control)] border px-3.5 py-2.5"
        style={{
          borderColor: "var(--color-border)",
          background: "var(--color-background)",
          color: "var(--color-foreground)",
        }}
        {...rest}
      />
    </label>
  );
}

export function Chip({ children, active = false, onClick }: {
  children: ReactNode;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="pressable rounded-full border px-3.5 py-1.5 text-sm font-semibold"
      style={{
        borderColor: active ? "var(--color-primary)" : "var(--color-border)",
        background: active ? "var(--color-primary)" : "transparent",
        color: active ? "var(--color-on-primary)" : "var(--color-foreground)",
      }}
    >
      {children}
    </button>
  );
}

export function EmptyState({ icon, title, action }: {
  icon: ReactNode;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <div style={{ color: "var(--color-muted-foreground)" }}>{icon}</div>
      <p className="max-w-xs text-base" style={{ color: "var(--color-muted-foreground)" }}>
        {title}
      </p>
      {action}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-base" style={{ color: "var(--color-muted-foreground)" }}>
      <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
        <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label}
    </div>
  );
}