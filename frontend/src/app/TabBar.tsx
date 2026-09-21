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

/** Bottom tab bar — 48px+ targets, one-handed reach (DESIGN.md §2). */
export function TabBar() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-card"
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