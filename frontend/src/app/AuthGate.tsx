"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { api, getToken } from "@/lib/api";

/** Client-side auth gate. Redirects to /login when unauthenticated. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await getToken();
      if (!token) {
        router.replace("/login/");
        return;
      }
      try {
        await api.me();
      } catch {
        if (!cancelled) {
          await import("@/lib/api").then((m) => m.setToken(null));
          router.replace("/login/");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, pathname]);

  return <>{children}</>;
}