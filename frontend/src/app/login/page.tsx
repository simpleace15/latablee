"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, getToken, setToken } from "@/lib/api";
import { Button, Input } from "@/components/ui";
import { UtensilsCrossed } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const invite = params.get("invite") || undefined;

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);

  // Invite links force registration flow with the token attached
  useEffect(() => {
    if (invite) setMode("register");
  }, [invite]);

  // First-ever run: no user exists -> switch to register mode automatically
  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        await api.me();
        router.replace("/");
      } catch {
        await setToken(null);
      }
    })();
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        const res = await api.register(name, password, invite);
        await setToken(res.token);
        router.replace(invite ? "/" : "/onboard/");
      } else {
        const res = await api.login(name, password);
        await setToken(res.access_token);
        router.replace("/");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6 pb-10">
      <div className="mb-8 flex flex-col items-center gap-3 text-center">
        <div
          className="flex h-16 w-16 items-center justify-center rounded-[20px]"
          style={{ background: "var(--color-primary)" }}
        >
          <UtensilsCrossed size={30} color="var(--color-on-primary)" aria-hidden />
          <span className="sr-only">LaTablée</span>
        </div>
        <h1 className="text-3xl">LaTablée</h1>
        <p className="text-base" style={{ color: "var(--color-muted-foreground)" }}>
          Self-hosted recipes & meal planning for the whole table
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        {invite && (
          <p
            className="rounded-[var(--radius-control)] border px-3.5 py-2.5 text-sm"
            style={{ borderColor: "var(--color-border)", color: "var(--color-muted-foreground)" }}
          >
            You've been invited to join a household — pick a name and password.
          </p>
        )}
        <Input
          label={mode === "login" ? "Name" : "Your name"}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="username"
          required
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          required
        />
        {error && (
          <p className="text-sm font-semibold" style={{ color: "var(--color-destructive)" }}>
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
        </Button>
        {!invite && (
          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="pressable text-sm font-semibold"
            style={{ color: "var(--color-muted-foreground)" }}
          >
            {mode === "login"
              ? "First time here? Set up your table"
              : "Already have an account? Sign in"}
          </button>
        )}
      </form>
    </main>
  );
}


export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
