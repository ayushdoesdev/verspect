"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FlaskConical, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { MigrationAssistantLanding } from "@/components/billing/migration-assistant-landing";
import { PremiumBadge } from "@/components/billing/premium-gate";
import {
  ErrorState,
  MigrationAssistantSkeleton,
  RefetchBar,
} from "@/components/loading";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NavLink } from "@/components/navigation/nav-link";
import { cn } from "@/lib/utils";

export default function MigrationAssistantPage() {
  const auth = useRequireAuth();
  const entitlements = useEntitlements();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const deps = useQuery({
    queryKey: ["dependencies", "migration-assistant"],
    queryFn: () => api.dependencies(`?page=1&page_size=12`),
    enabled: auth.isAuthenticated && entitlements.canGenerateAiMigration,
  });

  if (auth.isLoading || !auth.isAuthenticated || entitlements.loading) {
    return (
      <AppShell>
        <MigrationAssistantSkeleton />
      </AppShell>
    );
  }

  const locked = !entitlements.canGenerateAiMigration;
  const userLogin = auth.user?.github_login || me.data?.github_login;

  if (locked) {
    return (
      <AppShell userLogin={userLogin}>
        <MigrationAssistantLanding />
      </AppShell>
    );
  }

  if (deps.isLoading && !deps.data) {
    return (
      <AppShell userLogin={userLogin}>
        <MigrationAssistantSkeleton />
      </AppShell>
    );
  }

  if (deps.isError && !deps.data) {
    return (
      <AppShell userLogin={userLogin}>
        <PageHeader
          title="AI Migration Assistant"
          description="Generate precise code migrations for a dependency upgrade."
          actions={<PremiumBadge variant="team" />}
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
        title="AI Migration Assistant"
        description="Generate precise code migrations for a dependency upgrade."
        actions={<PremiumBadge variant="team" />}
      />
      <Card className="mb-6 border-primary/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-primary" />
            Run a migration analysis
          </CardTitle>
          <CardDescription>
            Open a dependency and use Upgrade Simulator → Migration Assistant to see current vs
            updated code, patches, and confidence.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/dependencies" className={cn(buttonVariants())}>
            Browse dependencies
          </Link>
        </CardContent>
      </Card>
      <RefetchBar active={deps.isFetching && !deps.isLoading} label="Updating packages…" />
      {!deps.data?.items?.length ? (
        <p className="text-sm text-muted-foreground">
          Import a repository and scan dependencies to start generating migrations.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {(deps.data?.items || []).map((d) => (
            <NavLink
              key={d.id}
              href={`/dependencies/${d.id}`}
              interactive="card"
              className="rounded-xl border border-border/70 bg-card/40 px-4 py-3 transition-colors hover:border-primary/40 hover:bg-accent/30"
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
