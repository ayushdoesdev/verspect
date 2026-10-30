"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useNavRouter } from "@/lib/nav-router";
import { formatScore, severityColor } from "@/lib/utils";
import { AppShell, EmptyState, PageHeader } from "@/components/layout/app-shell";
import { DashboardSkeleton, ErrorState, RefetchBar } from "@/components/loading";
import { NavLink } from "@/components/navigation/nav-link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { GitBranch } from "lucide-react";

const PIE_COLORS = ["#3dd6c6", "#6c9eff", "#e6b450", "#f07178", "#c3a6ff"];

export default function DashboardPage() {
  const router = useNavRouter();
  const auth = useRequireAuth();
  const dash = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
    enabled: auth.isAuthenticated,
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <DashboardSkeleton />
      </AppShell>
    );
  }

  if (dash.isLoading && !dash.data) {
    return (
      <AppShell userLogin={auth.user?.github_login}>
        <DashboardSkeleton />
      </AppShell>
    );
  }

  if (dash.isError && !dash.data) {
    return (
      <AppShell userLogin={auth.user?.github_login}>
        <PageHeader title="Overview" description="Dependency health across your workspace." />
        <ErrorState
          title="Unable to load dashboard"
          description={(dash.error as Error)?.message || "Try again in a moment."}
          onRetry={() => dash.refetch()}
        />
      </AppShell>
    );
  }

  if (!dash.data) {
    return (
      <AppShell userLogin={auth.user?.github_login}>
        <EmptyState
          title="No repositories yet"
          description="Connect GitHub to begin analyzing your repositories."
          icon={<GitBranch className="h-6 w-6" />}
          action={
            <Button onClick={() => router.push("/repositories")}>Connect GitHub</Button>
          }
        />
      </AppShell>
    );
  }

  const { stats, charts, latest_releases, critical_cves, recent_alerts } = dash.data;

  const statCards = [
    { label: "Repositories", value: stats.repository_count },
    { label: "Dependencies", value: stats.dependency_count },
    { label: "Outdated", value: stats.outdated_count },
    { label: "Vulnerable", value: stats.vulnerable_count },
    { label: "Critical", value: stats.critical_count },
    { label: "Health", value: formatScore(stats.average_health_score) },
  ];

  return (
    <AppShell userLogin={auth.user?.github_login}>
      <PageHeader
        title="Dashboard"
        description="Live risk posture across watched repositories."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <PrivateBetaBadge />
            <Button variant="secondary" onClick={() => router.push("/repositories")}>
              Manage repos
            </Button>
          </div>
        }
      />
      <RefetchBar active={dash.isFetching && !dash.isLoading} label="Updating dashboard…" />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {statCards.map((s, i) => (
          <Card key={s.label} className="animate-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
            <CardHeader className="pb-2">
              <CardDescription>{s.label}</CardDescription>
              <CardTitle className="text-2xl font-semibold tabular-nums">{s.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Dependency distribution</CardTitle>
            <CardDescription>By status</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={charts.dependency_distribution}
                  dataKey="value"
                  nameKey="label"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {charts.dependency_distribution.map((_, idx) => (
                    <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#121a24",
                    border: "1px solid #243044",
                    borderRadius: 8,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Outdated trend</CardTitle>
            <CardDescription>Version lag buckets</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts.outdated_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#243044" />
                <XAxis dataKey="label" tick={{ fill: "#8b9bb0", fontSize: 11 }} />
                <YAxis tick={{ fill: "#8b9bb0", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: "#121a24",
                    border: "1px solid #243044",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="value" fill="#e6b450" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Health scores</CardTitle>
            <CardDescription>Top repositories</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts.health_scores} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#243044" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: "#8b9bb0", fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={80}
                  tick={{ fill: "#8b9bb0", fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#121a24",
                    border: "1px solid #243044",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="value" fill="#3dd6c6" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Latest releases</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {latest_releases.length === 0 ? (
              <p className="text-sm text-muted-foreground">No release data yet.</p>
            ) : (
              latest_releases.slice(0, 6).map((r) => (
                <div key={r.id} className="flex items-start justify-between gap-2 border-b border-border/50 pb-2 last:border-0">
                  <div>
                    <div className="text-sm font-medium">{r.package_name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{r.version}</div>
                  </div>
                  {r.has_breaking_changes ? (
                    <Badge className="border-destructive/40 bg-destructive/10 text-destructive">Breaking</Badge>
                  ) : (
                    <Badge className="border-border text-muted-foreground">OK</Badge>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Critical CVEs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {critical_cves.length === 0 ? (
              <p className="text-sm text-muted-foreground">No critical vulnerabilities.</p>
            ) : (
              critical_cves.slice(0, 6).map((c) => (
                <NavLink
                  key={c.id}
                  href="/security"
                  interactive="row"
                  className="block border-b border-border/50 pb-2 last:border-0"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-destructive">{c.osv_id}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.cvss_score != null ? `CVSS ${c.cvss_score}` : ""}
                    </span>
                  </div>
                  <div className="mt-1 text-sm">{c.package_name}</div>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{c.summary}</p>
                </NavLink>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {recent_alerts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No alerts yet.</p>
            ) : (
              recent_alerts.slice(0, 6).map((a) => (
                <div key={a.id} className="border-b border-border/50 pb-2 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium uppercase ${severityColor(a.severity)}`}>
                      {a.severity}
                    </span>
                    <span className="text-xs text-muted-foreground">{a.alert_type}</span>
                  </div>
                  <div className="mt-1 text-sm">{a.title}</div>
                  {a.dependency_id ? (
                    <NavLink
                      href={`/dependencies/${a.dependency_id}`}
                      interactive="plain"
                      className="text-xs text-primary hover:underline"
                    >
                      View dependency
                    </NavLink>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
