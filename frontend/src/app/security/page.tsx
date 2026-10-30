"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Shield } from "lucide-react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { cn, severityColor } from "@/lib/utils";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { ErrorState, RefetchBar, SecuritySkeleton } from "@/components/loading";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { NavLink } from "@/components/navigation/nav-link";

export default function SecurityPage() {
  const auth = useRequireAuth();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const dash = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
    enabled: auth.isAuthenticated,
  });
  const deps = useQuery({
    queryKey: ["dependencies", { vulnerable: true }],
    queryFn: () =>
      api.dependencies(`?page=1&page_size=50&has_vulnerabilities=true&sort_by=risk_score&sort_order=desc`),
    enabled: auth.isAuthenticated,
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <SecuritySkeleton />
      </AppShell>
    );
  }

  if ((deps.isLoading && !deps.data) || (dash.isLoading && !dash.data)) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <SecuritySkeleton />
      </AppShell>
    );
  }

  if (deps.isError && !deps.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <PageHeader
          title="Security"
          description="CVE and advisory overview across your scanned repositories."
        />
        <ErrorState
          title="Unable to load security findings"
          description={(deps.error as Error)?.message || "Try again in a moment."}
          onRetry={() => deps.refetch()}
        />
      </AppShell>
    );
  }

  const vulnerable = deps.data?.items || [];
  const vulnerableCount = dash.data?.stats.vulnerable_count ?? deps.data?.total ?? vulnerable.length;
  const advisoryCount = vulnerable.reduce((n, d) => n + (d.vulnerability_count || 0), 0);
  const osvUnavailable = dash.data?.stats.osv_unavailable_count || 0;

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader
        title="Security"
        description="CVE and advisory overview across your scanned repositories."
      />
      <RefetchBar active={deps.isFetching && !deps.isLoading} label="Updating security findings…" />
      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <p className="text-xs text-muted-foreground">Vulnerable packages</p>
            <CardTitle className="text-2xl tabular-nums">{vulnerableCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-xs text-muted-foreground">Advisories on this page</p>
            <CardTitle className="text-2xl tabular-nums">{advisoryCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-xs text-muted-foreground">Coverage</p>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4 text-primary" />
              {osvUnavailable > 0
                ? `Security data unavailable for ${osvUnavailable} package${osvUnavailable === 1 ? "" : "s"}`
                : "OSV scan completed for scanned packages"}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="space-y-2">
        {vulnerable.map((d) => (
          <NavLink
            key={d.id}
            href={`/dependencies/${d.id}`}
            interactive="row"
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/70 px-4 py-3 hover:bg-accent/30"
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              <span className="font-medium">{d.package_name}</span>
              <span className="font-mono text-xs text-muted-foreground">
                {d.current_version || "unpinned"}
              </span>
            </div>
            <Badge className={cn("border", severityColor("high"))}>
              {d.vulnerability_count || 1} CVE{(d.vulnerability_count || 1) === 1 ? "" : "s"}
            </Badge>
          </NavLink>
        ))}
        {!vulnerable.length && osvUnavailable > 0 ? (
          <p className="text-sm text-muted-foreground">
            Security data is unavailable for some packages, so this list cannot confirm that
            there are no vulnerabilities. Retry the repository scan.
          </p>
        ) : null}
        {!vulnerable.length && osvUnavailable === 0 ? (
          <p className="text-sm text-muted-foreground">
            No vulnerable packages found in the current scan set.
          </p>
        ) : null}
      </div>
    </AppShell>
  );
}
