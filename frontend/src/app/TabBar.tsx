"use client";

import { CalendarDays, ChefHat, ListCheck, Settings, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/", label: "Today", icon: Sun },
  { href: "/plan", label: "Plan", icon: CalendarDays },
  { href: "/recipes", label: "Recipes", icon: ChefHat },
  { href: "/list", label: "List", icon: ListCheck },
  { href: "/settings", label: "Settings", icon: Settings },
];

/** Bottom tab bar on mobile; hidden on lg+ (sidebar takes over). 48px+ targets. */
export function TabBar() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-card lg:hidden"
      style={{ borderColor: "var(--color-border)" }}
    >
      <div className="mx-auto flex max-w-xl">
        {tabs.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className="pressable flex flex-1 flex-col items-center gap-1 py-2.5 text-xs"
              style={{
                color: active ? "var(--color-primary)" : "var(--color-muted-foreground)",
              }}
            >
              <Icon size={22} strokeWidth={active ? 2.4 : 2} aria-hidden />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/** Left sidebar for desktop (lg+): persistent nav, same destinations. */
export function SideNav() {
  const pathname = usePathname();
  return (
    <aside
      aria-label="Main"
      className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r bg-card px-4 py-6 lg:flex"
      style={{ borderColor: "var(--color-border)" }}
    >
      <p className="mb-8 px-2 font-heading text-2xl" style={{ color: "var(--color-primary)" }}>
        LaTablée
      </p>
      <nav className="flex flex-col gap-1.5">
        {tabs.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className="pressable flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2.5 text-base font-semibold"
              style={{
                background: active ? "var(--color-muted)" : "transparent",
                color: active ? "var(--color-primary)" : "var(--color-foreground)",
              }}
            >
              <Icon size={20} strokeWidth={active ? 2.4 : 2} aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>
      <p className="mt-auto px-3 text-xs" style={{ color: "var(--color-muted-foreground)" }}>
        Self-hosted · for the whole table
      </p>
    </aside>
  );
}