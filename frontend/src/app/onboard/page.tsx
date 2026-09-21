"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Input, Spinner } from "@/components/ui";

const TIMEZONES = [
  "America/Denver", "America/Chicago", "America/New_York", "America/Los_Angeles",
  "America/Phoenix", "UTC", "Europe/London", "Europe/Paris", "Australia/Sydney",
];

export default function OnboardPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // wizard state
  const [name, setName] = useState("My household");
  const [timezone, setTimezone] = useState("America/Denver");
  const [allergies, setAllergies] = useState("");
  const [dislikes, setDislikes] = useState("");
  const [favorites, setFavorites] = useState("");
  const [remember, setRemember] = useState("");
  const [userRole, setUserRole] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const u = await api.me();
        setUserRole(u.role);
        if (u.household_id) {
          router.replace("/"); // already onboarded
          return;
        }
      } catch {
        router.replace("/login/");
        return;
      }
      try {
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (tz) setTimezone(tz);
      } catch {
        /* keep default */
      }
      setLoading(false);
    })();
  }, [router]);

  async function finish() {
    setBusy(true);
    setError("");
    try {
      await api.onboard({
        name,
        timezone,
        allergies: split(allergies),
        dislikes: split(dislikes),
        favorites: split(favorites),
        things_to_remember: remember,
      });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save — try again");
      setBusy(false);
    }
  }

  function split(s: string) {
    return s.split(",").map((x) => x.trim()).filter(Boolean);
  }

  if (loading) return <Spinner label="Loading…" />;
  if (userRole !== "admin") {
    return (
      <main className="mx-auto max-w-md px-6 pt-24 text-center">
        <h1 className="text-2xl">Waiting for your household admin</h1>
        <p className="mt-3 text-base" style={{ color: "var(--color-muted-foreground)" }}>
          Only the first account completes setup. You can sign in once they've finished.
        </p>
      </main>
    );
  }

  const steps = [
    // Step 1 — name the household
    <div key="s1" className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl">Welcome to your table</h1>
        <p className="mt-1 text-base" style={{ color: "var(--color-muted-foreground)" }}>
          What should we call your household? This is just for you and yours.
        </p>
      </div>
      <Input label="Household name" value={name} onChange={(e) => setName(e.target.value)} required />
    </div>,

    // Step 2 — allergies & dislikes (feeds AI suggestions)
    <div key="s2" className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl">Anything to avoid?</h1>
        <p className="mt-1 text-base" style={{ color: "var(--color-muted-foreground)" }}>
          Allergies are taken seriously everywhere in the app. Comma-separated, skip if none.
        </p>
      </div>
      <Input label="Allergies" value={allergies} onChange={(e) => setAllergies(e.target.value)}
        placeholder="peanuts, shellfish" />
      <Input label="Dislikes (we'll steer around them)" value={dislikes}
        onChange={(e) => setDislikes(e.target.value)} placeholder="olives, blue cheese" />
    </div>,

    // Step 3 — favorites & notes
    <div key="s3" className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl">What do you love?</h1>
        <p className="mt-1 text-base" style={{ color: "var(--color-muted-foreground)" }}>
          Favorites steer suggestions (not rules). Anything else the app should remember?
        </p>
      </div>
      <Input label="Favorites" value={favorites} onChange={(e) => setFavorites(e.target.value)}
        placeholder="tacos, sheet-pan dinners" />
      <Input label="Things to remember (optional)" value={remember}
        onChange={(e) => setRemember(e.target.value)}
        placeholder="Kids hate spice. Keep weeknights under 40 minutes." />
    </div>,

    // Step 4 — timezone + invite
    <div key="s4" className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl">Almost done</h1>
        <p className="mt-1 text-base" style={{ color: "var(--color-muted-foreground)" }}>
          "Tonight" follows your timezone. Invite your people by link after setup.
        </p>
      </div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-semibold">Timezone</span>
        <select
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          className="w-full rounded-[var(--radius-control)] border px-3.5 py-2.5"
          style={{ borderColor: "var(--color-border)", background: "var(--color-background)", color: "var(--color-foreground)" }}
        >
          {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
        </select>
      </label>
    </div>,
  ];

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col px-6 pb-8 pt-10">
      <div className="mb-6 flex gap-2">
        {steps.map((_, i) => (
          <div
            key={i}
            className="h-1.5 flex-1 rounded-full"
            style={{ background: i <= step ? "var(--color-primary)" : "var(--color-muted)" }}
          />
        ))}
      </div>
      {steps[step]}
      {error && (
        <p className="mt-4 text-sm font-semibold" style={{ color: "var(--color-destructive)" }}>{error}</p>
      )}
      <div className="mt-auto flex gap-3 pt-8">
        {step > 0 && (
          <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={busy}>
            Back
          </Button>
        )}
        {step < steps.length - 1 ? (
          <Button className="flex-1" size="lg" onClick={() => setStep(step + 1)} disabled={busy}>
            Next
          </Button>
        ) : (
          <Button className="flex-1" size="lg" onClick={finish} disabled={busy}>
            {busy ? "Setting up…" : "Set my table"}
          </Button>
        )}
      </div>
    </main>
  );
}
