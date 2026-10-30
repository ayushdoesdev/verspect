"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Sparkles } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { formatScore, severityColor, statusBadge } from "@/lib/utils";
import { useJobs } from "@/lib/jobs/jobs-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  DependencyPageSkeleton,
  ErrorState,
  LoadingButton,
  RefetchBar,
} from "@/components/loading";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UpgradeSimulator } from "@/components/dependencies/upgrade-simulator";
import {
  PremiumBadge,
  PremiumUpgradeModal,
} from "@/components/billing/premium-gate";
import type { DependencyDetail } from "@/types";

export default function DependencyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { toast } = useJobs();
  const auth = useRequireAuth();
  const entitlements = useEntitlements();
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const dep = useQuery({
    queryKey: ["dependency", id],
    queryFn: () => api.dependency(id),
    enabled: auth.isAuthenticated && !!id,
  });
  const repo = useQuery({
    queryKey: ["repository", dep.data?.repository_id],
    queryFn: () => api.repository(dep.data!.repository_id),
    enabled: auth.isAuthenticated && !!dep.data?.repository_id,
  });
  const repoArchived = !!repo.data?.is_archived;

  const refreshAi = useMutation({
    mutationFn: () => api.refreshAi(id),
    onSuccess: () => {
      toast("Preparing AI insights…", { tone: "info" });
      setTimeout(() => qc.invalidateQueries({ queryKey: ["dependency", id] }), 2000);
    },
    onError: (err) => {
      if (err instanceof ApiError && (err.status === 403 || err.status === 402)) {
        setUpgradeOpen(true);
        return;
      }
      toast("AI unavailable", {
        tone: "error",
        description: (err as Error).message,
        actionLabel: "Retry",
      });
    },
  });

  const userLogin = auth.user?.github_login || me.data?.github_login;

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <DependencyPageSkeleton />
      </AppShell>
    );
  }

  if (dep.isError && !dep.data) {
    return (
      <AppShell userLogin={userLogin}>
        <ErrorState
          title="Unable to load dependency"
          description={(dep.error as Error).message || "Failed to load dependency"}
          onRetry={() => dep.refetch()}
        />
      </AppShell>
    );
  }

  if (!dep.data) {
    return (
      <AppShell userLogin={userLogin}>
        <DependencyPageSkeleton />
      </AppShell>
    );
  }

  const d = dep.data as DependencyDetail;
  const advisor = d.upgrade_advisor;
  const canAi = entitlements.aiEnabled;
  const docs = d.documentation_links?.length
    ? d.documentation_links
    : [
        {
          label: "PyPI",
          url: d.pypi_url || `https://pypi.org/project/${encodeURIComponent(d.package_name)}/`,
        },
      ].concat(
        d.github_repo_url || d.home_page
          ? [{ label: d.github_repo_url ? "GitHub" : "Homepage", url: (d.github_repo_url || d.home_page)! }]
          : [],
      );

  return (
    <AppShell userLogin={userLogin}>
      <PremiumUpgradeModal
        open={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        variant="pro"
      />
      <RefetchBar active={dep.isFetching && !dep.isLoading} label="Updating dependency analysis…" />
      <PageHeader
        title={d.package_name}
        description={d.summary || "Package intelligence"}
        actions={
          <span
            title={
              repoArchived
                ? "Restore the repository to run new analysis"
                : undefined
            }
          >
            <LoadingButton
              onClick={() => {
                if (repoArchived) return;
                if (!canAi) {
                  setUpgradeOpen(true);
                  return;
                }
                refreshAi.mutate();
              }}
              loading={canAi && refreshAi.isPending}
              loadingText="Generating…"
              disabled={repoArchived && !refreshAi.isPending}
            >
              <Sparkles className="h-4 w-4" />
              {canAi ? "Refresh AI" : "Unlock AI"}
            </LoadingButton>
          </span>
        }
      />

      <div className="mb-6 flex flex-wrap gap-2">
        <Badge className={statusBadge(d.status)}>{d.status.replaceAll("_", " ")}</Badge>
        <Badge className="border-border font-mono text-muted-foreground">
          {d.current_version || "unpinned"} → {d.latest_version || "?"}
        </Badge>
        {d.is_outdated ? (
          <Badge className="border-warning/40 bg-warning/10 text-warning">Outdated</Badge>
        ) : (
          <Badge className="border-success/40 bg-success/10 text-success">Up to date</Badge>
        )}
        {d.license_spdx ? (
          <Badge className="border-border text-muted-foreground">{d.license_spdx}</Badge>
        ) : null}
        <Badge className="border-primary/30 bg-primary/10 text-primary">
          Health {formatScore(d.health_score)}
        </Badge>
        <Badge className="border-border text-muted-foreground">
          Risk {formatScore(d.risk_score)}
        </Badge>
        <Badge className="border-border text-muted-foreground">
          {d.usage_count} usages · {d.file_count} files
        </Badge>
      </div>

      {d.health_breakdown ? (
        <Card className="mb-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Health breakdown</CardTitle>
            <CardDescription>
              Deterministic score factors — not AI. Overall{" "}
              {formatScore(d.health_breakdown.overall ?? d.health_score)}
              {d.health_breakdown.data_quality
                ? ` · ${d.health_breakdown.data_quality} data`
                : ""}
              {d.health_breakdown.completeness != null
                ? ` · ${Math.round(d.health_breakdown.completeness * 100)}% of signals observed`
                : ""}
              .
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(
              [
                ["Security", d.health_breakdown.security],
                ["Maintenance", d.health_breakdown.maintenance],
                ["Freshness", d.health_breakdown.freshness],
                ["License", d.health_breakdown.license],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-md border border-border/50 p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{formatScore(value)}</div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.min(100, Number(value ?? 0))}%` }}
                  />
                </div>
              </div>
            ))}
            </div>
            {(d.health_breakdown.missing_signals || []).length > 0 ? (
              <p className="mt-3 text-xs text-muted-foreground">
                Not observed for this package: {(d.health_breakdown.missing_signals || []).join(", ")}.
                Those signals are omitted from the score rather than guessed.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {(d.introduced_by || []).length > 0 ? (
        <Card className="mb-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Introduced by</CardTitle>
            <CardDescription>Direct parents that pull this package into the graph</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {d.introduced_by!.map((p) => (
              <Badge key={p.parent_dependency_id} className="border-border font-mono text-muted-foreground">
                {p.parent_package}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Current", d.current_version || "unpinned"],
          ["Latest", d.latest_version || "—"],
          ["Health", formatScore(d.health_score)],
          ["Risk", formatScore(d.risk_score)],
        ].map(([label, value]) => (
          <Card key={label as string}>
            <CardHeader className="pb-2">
              <p className="text-xs text-muted-foreground">{label}</p>
              <CardTitle className="text-xl tabular-nums font-mono">{value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      {advisor ? (
        <Card className="mb-6 border-primary/20">
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle>AI Upgrade Advisor</CardTitle>
              <PremiumBadge variant={canAi ? "pro" : "locked"} />
            </div>
            <CardDescription>
              Confidence: {advisor.confidence_label} ({Math.round((advisor.confidence || 0) * 100)}
              %) — {advisor.confidence_reason}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Should I upgrade?
              </div>
              <p className="text-sm text-foreground">{advisor.should_i_upgrade}</p>
              <Badge className="mt-2 border-primary/30 bg-primary/10 text-primary">
                {advisor.immediate_action}
              </Badge>
              {advisor.recommended_version ? (
                <p className="mt-2 font-mono text-xs text-muted-foreground">
                  Recommended: {advisor.recommended_version} · Effort: {advisor.estimated_effort}
                </p>
              ) : null}
            </div>
            <div className="space-y-3 text-sm">
              <List title="Why" items={advisor.why || []} />
              <List title="Benefits" items={advisor.benefits || []} />
              <List title="Risks" items={advisor.risks || []} />
            </div>
          </CardContent>
        </Card>
      ) : null}

      <UpgradeSimulator
        dependencyId={d.id}
        packageName={d.package_name}
        currentVersion={d.current_version}
        latestVersion={d.latest_version}
        readOnlyReason={
          repoArchived
            ? "Repository is archived — historical simulations remain available. Restore the repository to run new analysis."
            : null
        }
      />

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Overview</CardTitle>
            <CardDescription>
              {canAi ? "AI explanation" : "Package summary"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p className="text-foreground">
              {canAi
                ? d.ai_explanation ||
                  d.summary ||
                  `${d.package_name} is tracked in this repository with ${d.usage_count} API usage site(s).`
                : d.summary ||
                  `${d.package_name} is tracked in this repository with ${d.usage_count} API usage site(s).`}
            </p>
            {canAi ? (
              <div>
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Should I update?
                </div>
                <p>
                  {d.ai_should_update ||
                    advisor?.should_i_upgrade ||
                    "Refresh AI for a recommendation."}
                </p>
              </div>
            ) : null}
            <div>
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Security summary
              </div>
              <p>
                {d.ai_security_summary && canAi
                  ? d.ai_security_summary
                  : d.osv_status === "unavailable"
                    ? "Security data unavailable — OSV could not be queried for this package."
                    : d.vulnerability_count
                      ? `${d.vulnerability_count} known advisories for the installed version.`
                      : "No known vulnerabilities for the installed version."}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Official documentation</CardTitle>
            <CardDescription>Clickable references</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {docs.map((link) => (
              <a
                key={link.url}
                href={link.url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 rounded-md border border-border/60 px-3 py-2 text-sm text-primary hover:bg-accent/40"
              >
                <span className="text-xs text-muted-foreground">{link.label}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{link.url}</span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0" />
              </a>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Security</CardTitle>
            <CardDescription>{d.vulnerability_count} vulnerabilities</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {d.cves.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No known vulnerabilities for the installed version.
              </p>
            ) : (
              d.cves.map((c) => (
                <div key={c.id} className="rounded-md border border-border/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs">{c.osv_id}</span>
                    <span className={`text-xs uppercase ${severityColor(c.severity)}`}>
                      {c.severity}
                    </span>
                  </div>
                  <p className="mt-1 text-sm">{c.summary}</p>
                  {c.fixed_version ? (
                    <p className="mt-1 text-xs text-success">Fixed in {c.fixed_version}</p>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Alternatives</CardTitle>
            <CardDescription>Popularity · maintenance · migration effort</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {d.alternatives.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No better alternative identified for this package. It may already be the best fit,
                or the knowledge base has not learned alternatives yet.
              </p>
            ) : (
              d.alternatives.map((a) => (
                <div key={a.id} className="rounded-md border border-border/60 p-3">
                  <div className="font-medium">{a.alternative_name}</div>
                  <p className="mt-1 text-sm text-muted-foreground">{a.reason}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <Badge className="border-border text-muted-foreground">
                      Effort: {a.migration_effort}
                    </Badge>
                    {a.popularity_score != null ? (
                      <Badge className="border-border text-muted-foreground">
                        Popularity {formatScore(a.popularity_score)}
                      </Badge>
                    ) : null}
                    {a.health_score != null ? (
                      <Badge className="border-border text-muted-foreground">
                        Health {formatScore(a.health_score)}
                      </Badge>
                    ) : null}
                    {a.confidence != null ? (
                      <Badge className="border-border text-muted-foreground">
                        Conf {Math.round(a.confidence * 100)}%
                      </Badge>
                    ) : null}
                  </div>
                  {a.pros?.length ? (
                    <p className="mt-2 text-xs text-success">Pros: {a.pros.join(" · ")}</p>
                  ) : null}
                  {a.cons?.length ? (
                    <p className="mt-1 text-xs text-warning">Cons: {a.cons.join(" · ")}</p>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Breaking changes & releases</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {d.releases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No analyzed releases yet. Run a scan or Refresh AI after versions are known.
              </p>
            ) : (
              d.releases.map((r) => (
                <div key={r.id} className="rounded-md border border-border/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm">{r.version}</span>
                    {r.has_breaking_changes ? (
                      <Badge className="border-destructive/40 bg-destructive/10 text-destructive">
                        Breaking
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {r.ai_summary || "Release recorded — summary pending."}
                  </p>
                  {r.breaking_changes?.length ? (
                    <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-destructive">
                      {r.breaking_changes.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {d.migration_reports.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Migration reports</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {d.migration_reports.map((m) => (
                <div key={m.id} className="rounded-md border border-border/60 p-4">
                  <h4 className="font-medium">{m.title}</h4>
                  <p className="mt-1 text-sm text-muted-foreground">{m.summary}</p>
                  {m.step_by_step?.length ? (
                    <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
                      {m.step_by_step.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                  ) : null}
                  {m.recommendation ? (
                    <p className="mt-3 text-sm text-primary">{m.recommendation}</p>
                  ) : null}
                </div>
              ))}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Affected files</CardTitle>
              <CardDescription>From AST usage index</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="mb-3 text-sm text-muted-foreground">
                {d.file_count} file(s) · {d.usage_count} usage site(s). Expand the API usage table
                below for symbols and line numbers.
              </p>
              <div className="flex flex-wrap gap-1">
                {[...new Set(d.usages.map((u) => u.file_path))].slice(0, 12).map((f) => (
                  <Badge key={f} className="border-border font-mono text-muted-foreground">
                    {f}
                  </Badge>
                ))}
                {!d.usages.length ? (
                  <p className="text-sm text-muted-foreground">
                    No usage sites detected in scanned source files.
                  </p>
                ) : null}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>API usage</CardTitle>
          <CardDescription>
            {d.usages.length} sites across {d.file_count} files — static analysis of scanned source
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="pb-2">Symbol</th>
                <th className="pb-2">Kind</th>
                <th className="pb-2">File</th>
                <th className="pb-2">Line</th>
                <th className="pb-2">Context</th>
              </tr>
            </thead>
            <tbody>
              {d.usages.map((u) => (
                <tr key={u.id} className="border-b border-border/40">
                  <td className="py-2 font-mono text-xs">{u.fully_qualified_name}</td>
                  <td className="py-2 text-xs text-muted-foreground">{u.usage_kind}</td>
                  <td className="py-2 font-mono text-xs">{u.file_path}</td>
                  <td className="py-2 tabular-nums">{u.line}</td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {[u.enclosing_class, u.enclosing_function].filter(Boolean).join(".") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!d.usages.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No usage sites detected in scanned source files.
            </p>
          ) : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <ul className="list-disc space-y-1 pl-4 text-muted-foreground">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
