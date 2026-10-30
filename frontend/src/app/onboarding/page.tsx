"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { ErrorState, ListSkeleton, LoadingCopy, SessionSkeleton } from "@/components/loading";

const steps = [
  {
    id: 1,
    title: "Welcome",
    body: "Start a 7-day evaluation — no credit card. Analyze dependency upgrades before you ship.",
  },
  {
    id: 2,
    title: "Connect GitHub",
    body: "Authorize GitHub so we can import the repositories you own.",
  },
  {
    id: 3,
    title: "Import repositories",
    body: "Pick one repository for your evaluation (Python, JavaScript/TypeScript, Go, Java, Rust, PHP, or Ruby). Upgrade anytime for more.",
  },
  {
    id: 4,
    title: "Start first scan",
    body: "We’ll index dependencies, usage sites, and security signals.",
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const auth = useRequireAuth();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: api.usage,
    enabled: auth.isAuthenticated,
    retry: false,
  });
  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const repos = useQuery({
    queryKey: ["github-repos"],
    queryFn: api.githubRepos,
    enabled: step >= 3 && auth.isAuthenticated,
    retry: false,
  });

  const repoLimit = usage.data?.repositories_limit ?? 1;
  const reposUsed = usage.data?.repositories_used ?? 0;
  const slotsLeft =
    repoLimit == null ? Number.POSITIVE_INFINITY : Math.max(0, repoLimit - reposUsed);
  const atCapacity = slotsLeft <= 0;

  useEffect(() => {
    if (me.data?.onboarding_completed) router.replace("/dashboard");
  }, [me.data, router]);

  function toggleRepo(id: number, checked: boolean) {
    setError(null);
    if (!checked) {
      setSelected((prev) => prev.filter((x) => x !== id));
      return;
    }
    if (repoLimit != null && selected.length >= slotsLeft) {
      setError(
        `Evaluation includes ${repoLimit} repository. Select one to continue, or upgrade to Starter (10 repos) / Pro (unlimited).`,
      );
      // Replace selection with the newly chosen repo when limit is 1
      if (slotsLeft === 1) {
        setSelected([id]);
        setError(null);
      }
      return;
    }
    setSelected((prev) => [...prev, id]);
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      const toImport = selected.slice(0, slotsLeft === Number.POSITIVE_INFINITY ? selected.length : slotsLeft);
      if (toImport.length) {
        await api.importRepos(toImport);
      }
      await api.updateSettings({ onboarding_completed: true } as never);
      router.push("/dashboard");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Import failed";
      setError(message);
      setBusy(false);
    }
  }

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <SessionSkeleton variant="repositories" />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader title="Welcome" description="A short setup to get your first scan running." />
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex gap-2">
          {steps.map((s) => (
            <div
              key={s.id}
              className={`h-1.5 flex-1 rounded-full ${step >= s.id ? "bg-primary" : "bg-muted"}`}
            />
          ))}
        </div>
        <div className="rounded-xl border border-border/70 bg-card/60 p-6">
          <h2 className="text-xl font-semibold">{steps[step - 1].title}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{steps[step - 1].body}</p>

          {step === 2 ? (
            <Button className="mt-6" onClick={() => setStep(3)}>
              Continue with connected GitHub
            </Button>
          ) : null}

          {step === 3 ? (
            <div className="mt-6 space-y-3">
              <p className="text-xs text-muted-foreground">
                {repoLimit == null
                  ? "Your plan allows unlimited repositories."
                  : `Your plan allows ${repoLimit} repositor${repoLimit === 1 ? "y" : "ies"} (${reposUsed} used).`}{" "}
                {atCapacity ? (
                  <>
                    You’re at the limit —{" "}
                    <Link href="/billing" className="text-primary underline">
                      upgrade
                    </Link>{" "}
                    to Starter (10 repos) or Pro (unlimited), or skip import for now.
                  </>
                ) : repoLimit === 1 ? (
                  "Select one repository for your first scan."
                ) : null}
              </p>
              <div className="max-h-72 space-y-2 overflow-auto">
                {repos.isLoading && !repos.data ? (
                  <div className="space-y-2">
                    <LoadingCopy>Loading repositories…</LoadingCopy>
                    <ListSkeleton rows={5} />
                  </div>
                ) : null}
                {repos.isError && !repos.data ? (
                  <ErrorState
                    title="Unable to list GitHub repositories"
                    description="Connect GitHub from Settings if repositories cannot be listed."
                    onRetry={() => repos.refetch()}
                  />
                ) : null}
                {(repos.data || []).slice(0, 40).map((r) => {
                  const checked = selected.includes(r.github_repo_id) || r.already_imported;
                  return (
                    <label
                      key={r.github_repo_id}
                      className="flex items-center gap-3 rounded-md border border-border/60 px-3 py-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        disabled={r.already_imported || (atCapacity && !checked)}
                        checked={checked}
                        onChange={(e) => toggleRepo(r.github_repo_id, e.target.checked)}
                      />
                      <span className="font-mono">{r.full_name}</span>
                      {r.already_imported ? (
                        <span className="text-xs text-muted-foreground">imported</span>
                      ) : null}
                    </label>
                  );
                })}
              </div>
            </div>
          ) : null}

          {step === 4 && selected.length === 0 && !atCapacity ? (
            <p className="mt-4 text-sm text-amber-600 dark:text-amber-400">
              No repository selected. You can still finish setup and import later from Repositories.
            </p>
          ) : null}

          {error ? (
            <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}{" "}
              {error.toLowerCase().includes("upgrade") || error.toLowerCase().includes("plan") ? (
                <Link href="/billing" className="underline">
                  View plans
                </Link>
              ) : null}
            </div>
          ) : null}

          <div className="mt-8 flex justify-between">
            <Button variant="ghost" disabled={step === 1 || busy} onClick={() => setStep((s) => s - 1)}>
              Back
            </Button>
            {step < 4 ? (
              <Button onClick={() => setStep((s) => s + 1)}>Continue</Button>
            ) : (
              <Button onClick={finish} disabled={busy}>
                {busy ? "Starting…" : selected.length ? "Start scanning" : "Finish setup"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
