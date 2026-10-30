"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { PremiumBadge } from "@/components/billing/premium-gate";
import { ErrorState, RefetchBar, UpgradeSimulatorSkeleton } from "@/components/loading";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NavLink } from "@/components/navigation/nav-link";
import { cn } from "@/lib/utils";

export default function UpgradeSimulatorPage() {
  const auth = useRequireAuth();
  const entitlements = useEntitlements();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const deps = useQuery({
    queryKey: ["dependencies", "upgrade-simulator"],
    queryFn: () => api.dependencies(`?page=1&page_size=20`),
    enabled: auth.isAuthenticated,
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <UpgradeSimulatorSkeleton />
      </AppShell>
    );
  }

  const canSimulate = entitlements.upgradeSimulator;
  const userLogin = auth.user?.github_login || me.data?.github_login;

  if (deps.isLoading && !deps.data) {
    return (
      <AppShell userLogin={userLogin}>
        <UpgradeSimulatorSkeleton />
      </AppShell>
    );
  }

  if (deps.isError && !deps.data) {
    return (
      <AppShell userLogin={userLogin}>
        <PageHeader
          title="Upgrade Simulator"
          description="Analyze dependency upgrades — risk, breaking changes, security, and recommendations."
        />
        <ErrorState
          title="Unable to load packages"
          description={(deps.error as Error)?.message || "Try again in a moment."}
          onRetry={() => deps.refetch()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={userLogin}>
      <PageHeader
        title="Upgrade Simulator"
        description="Analyze dependency upgrades — risk, breaking changes, security, and recommendations. Available during active evaluation and on paid plans. AI Migration Assistant (code generation) is a separate Team feature."
        actions={!canSimulate ? <PremiumBadge variant="locked" /> : null}
      />

      {!canSimulate && !entitlements.loading ? (
        <Card className="mb-6 border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle className="text-base">
              {entitlements.evaluationExpired
                ? "Evaluation ended — Simulator paused"
                : "Upgrade Simulator unavailable"}
            </CardTitle>
            <CardDescription>
              {entitlements.evaluationExpired
                ? "Previous simulation reports remain visible. Upgrade to Starter or higher to run new analyses. AI Migration Assistant unlocks separately on Team."
                : "Upgrade Simulator requires an active evaluation or paid plan. AI Migration Assistant unlocks separately on Team."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Link href="/billing?plan=starter" className={cn(buttonVariants())}>
              Upgrade to Starter
            </Link>
            <Link href="/pricing" className={cn(buttonVariants({ variant: "outline" }))}>
              Compare plans
            </Link>
          </CardContent>
        </Card>
      ) : null}

      <RefetchBar
        active={deps.isFetching && !deps.isLoading}
        label="Updating packages…"
      />

      {!deps.data?.items?.length ? (
        <p className="text-sm text-muted-foreground">
          No dependencies yet. Import a repository and run a scan first.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {(deps.data?.items || []).map((d) => (
            <NavLink
              key={d.id}
              href={`/dependencies/${d.id}`}
              interactive="card"
              className="rounded-xl border border-border/70 bg-card/40 px-4 py-3 transition-colors hover:border-primary/40"
            >
              <div className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-primary" />
                <span className="font-medium">{d.package_name}</span>
              </div>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {d.current_version || "unpinned"} → {d.latest_version || "?"}
              </p>
            </NavLink>
          ))}
        </div>
      )}
    </AppShell>
  );
}
