"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { ErrorState, RefetchBar, UsageSkeleton } from "@/components/loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function UsagePage() {
  const auth = useRequireAuth();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const usage = useQuery({ queryKey: ["usage"], queryFn: api.usage, enabled: auth.isAuthenticated });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <UsageSkeleton />
      </AppShell>
    );
  }

  if (usage.isLoading && !usage.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <UsageSkeleton />
      </AppShell>
    );
  }

  if (usage.isError && !usage.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <PageHeader title="Usage" description="Plan consumption across repositories and seats." />
        <ErrorState
          title="Unable to load usage"
          description={(usage.error as Error)?.message || "Try again in a moment."}
          onRetry={() => usage.refetch()}
        />
      </AppShell>
    );
  }

  const u = usage.data;
  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader title="Usage" description="Plan consumption across repositories and seats." />
      <RefetchBar active={usage.isFetching && !usage.isLoading} label="Updating usage…" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          {
            title: "Repositories",
            value: `${u?.repositories_used ?? 0} / ${u?.repositories_limit ?? "∞"}`,
          },
          {
            title: "Seats",
            value: `${u?.members_used ?? 0} / ${u?.members_limit ?? "∞"}`,
          },
          {
            title: "Plan",
            value: u?.plan === "free" ? "Evaluation" : (u?.plan ?? "—"),
          },
          {
            title: "Access",
            value: u?.evaluation_expired
              ? "Evaluation ended (read-only)"
              : u?.read_only
                ? "Read-only"
                : u?.evaluation_active
                  ? "Evaluation active"
                  : "Active",
          },
          {
            title: "Upgrade Simulator",
            value: (u?.upgrade_simulator ?? true) ? "Enabled" : "Locked",
          },
          {
            title: "AI Upgrade Advisor (Pro+)",
            value: u?.ai_enabled ? "Enabled" : "Locked",
          },
          {
            title: "AI Migration Assistant (Team+)",
            value: u?.ai_migration_assistant || u?.can_generate_ai_migration ? "Enabled" : "Locked",
          },
          {
            title: "Scans (month)",
            value:
              u?.monthly_scan_limit == null
                ? `${u?.monthly_scans_used ?? 0} / ∞`
                : `${u?.monthly_scans_used ?? 0} / ${u.monthly_scan_limit}`,
          },
          {
            title: "AI migration requests (month)",
            value: String(u?.ai_migration_requests_this_month ?? 0),
          },
          {
            title: "AI tokens (month)",
            value: String(u?.ai_migration_tokens_this_month ?? 0),
          },
          {
            title: "Est. AI cost (month)",
            value: `$${(u?.ai_migration_cost_this_month ?? 0).toFixed(4)}`,
          },
          { title: "Teams", value: u?.teams_enabled ? "Enabled" : "Disabled" },
          { title: "GitHub webhooks", value: u?.webhooks ? "Enabled" : "Disabled" },
        ].map((card) => (
          <Card key={card.title}>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">{card.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold capitalize">{card.value}</CardContent>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
