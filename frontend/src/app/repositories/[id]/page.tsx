"use client";

import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowRight,
  Boxes,
  Check,
  FileCode2,
  Layers,
  Package,
  RefreshCw,
  Shield,
  Sparkles,
  Workflow,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { cn, formatScore, statusBadge } from "@/lib/utils";
import {
  classificationConfidence,
  classificationLanguage,
  dependencyManifest,
  hasClassification,
  hasPythonUpgradeCatalog,
  isAnalyzable,
  isUnsupported,
  supportActionTooltip,
  supportStatusLabel,
} from "@/lib/repository-support";
import { useJobs } from "@/lib/jobs/jobs-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { PremiumUpgradeModal } from "@/components/billing/premium-gate";
import {
  ErrorState,
  ListSkeleton,
  LoadingButton,
  LoadingCopy,
  RefetchBar,
  RepositoryPageSkeleton,
} from "@/components/loading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RepositoryActionsMenu } from "@/components/repositories/repository-actions";
import { NavLink } from "@/components/navigation/nav-link";
import type { Dependency, Repository } from "@/types";

export default function RepositoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { jobs, trackScan, toast } = useJobs();
  const auth = useRequireAuth();
  const entitlements = useEntitlements();
  const [depPage, setDepPage] = useState(1);
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  useEffect(() => {
    setDepPage(1);
  }, [id]);

  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const repo = useQuery({
    queryKey: ["repository", id],
    queryFn: () => api.repository(id),
    enabled: auth.isAuthenticated && !!id,
  });
  const deps = useQuery({
    queryKey: ["repo-deps", id, depPage],
    queryFn: () =>
      api.dependencies(
        `?repository_id=${id}&page=${depPage}&page_size=50&sort_by=package_name&sort_order=asc`,
      ),
    enabled: auth.isAuthenticated && !!id,
    placeholderData: keepPreviousData,
  });
  const insightDeps = useQuery({
    queryKey: ["repo-deps-insights", id],
    queryFn: () =>
      api.dependencies(
        `?repository_id=${id}&page=1&page_size=20&sort_by=risk_score&sort_order=desc`,
      ),
    enabled: auth.isAuthenticated && !!id,
  });
  const graph = useQuery({
    queryKey: ["repo-graph", id],
    queryFn: () => api.repositoryDependencyGraph(id),
    enabled: auth.isAuthenticated && !!id,
  });

  const scanMut = useMutation({
    mutationFn: () => api.triggerScan(id),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: ["repository", id] });
      qc.invalidateQueries({ queryKey: ["scans"] });
      const alreadyTracked = jobs.some((j) => j.resourceId === scan.id);
      trackScan(scan.id, {
        kind: "sync",
        title: "Syncing Repository…",
        subtitle: repo.data?.full_name || "Repository",
        repositoryId: id,
        showModal: true,
      });
      if (alreadyTracked) {
        toast("Scan already running", {
          tone: "info",
          description: "Monitoring the existing scan. Cancel or retry it from this window.",
        });
      } else {
        toast("Sync started", {
          tone: "info",
          description: "Fetching latest commits and re-analyzing dependencies…",
        });
      }
    },
    onError: (err) => {
      if (err instanceof ApiError && (err.status === 402 || err.status === 403)) {
        setUpgradeOpen(true);
        toast("Upgrade required", {
          tone: "error",
          description: err.detail || "Sync requires an active plan.",
          actionLabel: "Upgrade",
        });
        return;
      }
      toast("Sync failed", {
        tone: "error",
        description: (err as Error).message || "Unable to start scan",
        actionLabel: "Retry",
      });
    },
  });

  const items = useMemo(() => deps.data?.items || [], [deps.data?.items]);
  const insightItems = useMemo(
    () => insightDeps.data?.items || [],
    [insightDeps.data?.items],
  );
  const insights = useMemo(
    () => computeInsights(insightItems, repo.data),
    [insightItems, repo.data],
  );
  const userLogin = auth.user?.github_login || me.data?.github_login;
  const unsupported = repo.data ? isUnsupported(repo.data) : false;
  const analyzable = repo.data ? isAnalyzable(repo.data) : false;

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <RepositoryPageSkeleton />
      </AppShell>
    );
  }

  if (repo.isError && !repo.data) {
    return (
      <AppShell userLogin={userLogin}>
        <ErrorState
          title="Unable to load repository"
          description={(repo.error as Error).message || "Failed to load repository"}
          onRetry={() => repo.refetch()}
        />
      </AppShell>
    );
  }

  if (!repo.data) {
    return (
      <AppShell userLogin={userLogin}>
        <RepositoryPageSkeleton />
      </AppShell>
    );
  }

  const syncDisabled =
    unsupported || (!entitlements.canTriggerScans && !entitlements.canSyncRepositories);
  const syncTitle = unsupported
    ? supportActionTooltip(repo.data, "Repository Scan")
    : !entitlements.canTriggerScans && !entitlements.canSyncRepositories
      ? "Sync requires an active evaluation or paid plan."
      : undefined;

  return (
    <AppShell userLogin={userLogin}>
      <PremiumUpgradeModal
        open={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        variant={entitlements.evaluationExpired ? "evaluation" : "starter"}
      />
      <PageHeader
        title={repo.data.full_name}
        description={
          repo.data.is_archived
            ? "Archived · read-only · historical analysis retained"
            : !repo.data.is_watching
              ? "Sync paused · webhook and scheduled updates are off"
            : unsupported
              ? "Repository classified · no implemented analyzer for this ecosystem"
              : entitlements.evaluationExpired
                ? "Evaluation ended · existing analysis remains readable. Upgrade to run new scans."
                : repo.data.description || "Repository dependency overview"
        }
        actions={
          <>
            {repo.data.is_archived ? (
              <Badge className="border-warning/35 bg-warning/10 text-warning">Archived</Badge>
            ) : null}
            <Button variant="outline" onClick={() => window.open(repo.data.html_url, "_blank")}>
              GitHub
            </Button>
            {unsupported ? (
              <Link
                href="/roadmap"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-secondary/40 px-3 text-sm font-medium text-foreground transition hover:bg-accent"
              >
                View Roadmap <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : null}
            <span
              title={
                repo.data.is_archived
                  ? "Restore this repository to run syncs and new analysis"
                  : syncTitle
              }
            >
              <LoadingButton
                onClick={() => {
                  if (unsupported || repo.data.is_archived) return;
                  if (!entitlements.canTriggerScans && !entitlements.canSyncRepositories) {
                    setUpgradeOpen(true);
                    return;
                  }
                  scanMut.mutate();
                }}
                loading={scanMut.isPending}
                loadingText="Syncing…"
                disabled={(syncDisabled || !!repo.data.is_archived) && !scanMut.isPending}
              >
                <RefreshCw className="h-4 w-4" />
                Sync
              </LoadingButton>
            </span>
            <RepositoryActionsMenu repo={repo.data} hideViewDetails />
          </>
        }
      />

      {repo.data.is_archived ? (
        <Card className="mb-6 border-warning/25 bg-warning/5">
          <CardContent className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm">
              <div className="font-medium text-foreground">This repository is archived</div>
              <p className="mt-0.5 text-muted-foreground">
                Historical scans, dependencies, security findings, and reports remain available.
                Sync and new analysis are disabled until you restore it.
              </p>
            </div>
            <NavLink
              href="/repositories?lifecycle=archived"
              interactive="plain"
              className="shrink-0 text-sm font-medium text-primary hover:underline"
            >
              View in Archived
            </NavLink>
          </CardContent>
        </Card>
      ) : null}

      {hasClassification(repo.data) ? <ClassificationCard repo={repo.data} /> : null}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {(unsupported
          ? [
              ["Dependencies", "Not analyzed"],
              ["Outdated", "—"],
              ["Security", "Not analyzed"],
              ["License", "Not analyzed"],
              ["Health", "Unavailable"],
            ]
          : [
              ["Dependencies", String(repo.data.dependency_count)],
              ["Outdated", String(repo.data.outdated_count)],
              ["Vulnerable", String(repo.data.vulnerable_count)],
              ["License issues", String(repo.data.license_issues_count)],
              ["Health", formatScore(repo.data.health_score)],
            ]
        ).map(([label, value]) => (
          <Card key={label}>
            <CardHeader className="pb-2">
              <p className="text-xs text-muted-foreground">{label}</p>
              <CardTitle
                className={cn(
                  "text-xl",
                  unsupported ? "text-base font-medium text-muted-foreground" : "tabular-nums",
                )}
              >
                {value}
              </CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      {unsupported ? (
        <div className="mb-6 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Repository insights</CardTitle>
              <CardDescription>Available after ecosystem support ships</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                This repository has been classified successfully. Repository insights will become
                available once this ecosystem is supported.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recommended next upgrades</CardTitle>
              <CardDescription>Upgrade planning for this repository</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>Upgrade recommendations will be available after language support is released.</p>
              <div className="flex flex-wrap gap-2">
                <span title={supportActionTooltip(repo.data, "Upgrade Simulator")}>
                  <Button variant="outline" size="sm" disabled className="opacity-60">
                    <Workflow className="h-3.5 w-3.5" />
                    Upgrade Simulator
                  </Button>
                </span>
                <span title={supportActionTooltip(repo.data, "AI Migration Assistant")}>
                  <Button variant="outline" size="sm" disabled className="opacity-60">
                    <Sparkles className="h-3.5 w-3.5" />
                    AI Migration Assistant
                  </Button>
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="mb-6 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Repository insights</CardTitle>
              <CardDescription>Freshness, risk, and debt signals</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <InsightRow label="Dependency freshness" value={insights.freshnessLabel} />
              <InsightRow
                label="Highest risk"
                value={insights.highestRisk}
                href={insights.highestRiskId ? `/dependencies/${insights.highestRiskId}` : undefined}
              />
              <InsightRow
                label="Most used"
                value={insights.mostUsed}
                href={insights.mostUsedId ? `/dependencies/${insights.mostUsedId}` : undefined}
              />
              <InsightRow
                label="Most vulnerable"
                value={insights.mostVulnerable}
                href={
                  insights.mostVulnerableId
                    ? `/dependencies/${insights.mostVulnerableId}`
                    : undefined
                }
              />
              <InsightRow label="Technical debt estimate" value={insights.debtLabel} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recommended next upgrades</CardTitle>
              <CardDescription>Prioritized by security and outdated status</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {insights.recommended.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No urgent upgrades — dependencies look current, or scan has not completed yet.
                </p>
              ) : (
                insights.recommended.map((r) => (
                  <NavLink
                    key={r.id}
                    href={`/dependencies/${r.id}`}
                    interactive="row"
                    className="flex items-center justify-between gap-2 rounded-md border border-border/60 px-3 py-2 hover:bg-accent/40"
                  >
                    <div>
                      <div className="font-medium">{r.package_name}</div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {r.current_version || "unpinned"} → {r.latest_version || "?"}
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-1">
                      {r.has_vulnerabilities ? (
                        <Badge className="border-destructive/40 bg-destructive/10 text-destructive">
                          CVE
                        </Badge>
                      ) : null}
                      {r.is_outdated ? (
                        <Badge className="border-warning/40 bg-warning/10 text-warning">
                          outdated
                        </Badge>
                      ) : null}
                      <Badge className="border-border text-muted-foreground">
                        risk {formatScore(r.risk_score)}
                      </Badge>
                    </div>
                  </NavLink>
                ))
              )}
              <div className="flex flex-wrap gap-2 pt-3">
                <span
                  title={
                    entitlements.upgradeSimulator
                      ? supportActionTooltip(repo.data, "Upgrade Simulator")
                      : entitlements.evaluationExpired
                        ? "Upgrade Simulator is paused because the evaluation or plan ended."
                        : "Upgrade Simulator requires an active evaluation or paid plan."
                  }
                >
                  {entitlements.upgradeSimulator ? (
                    <NavLink
                      href="/upgrade-simulator"
                      interactive="plain"
                      className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-accent"
                    >
                      <Workflow className="h-3.5 w-3.5" />
                      Upgrade Simulator
                    </NavLink>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setUpgradeOpen(true)}
                    >
                      <Workflow className="h-3.5 w-3.5" />
                      Upgrade Simulator
                    </Button>
                  )}
                </span>
                <span
                  title={
                    entitlements.canGenerateAiMigration
                      ? supportActionTooltip(repo.data, "AI Migration Assistant")
                      : "AI Migration Assistant is available on Team when analysis exists. This is a plan entitlement, not a missing language analyzer."
                  }
                >
                  {entitlements.canGenerateAiMigration ? (
                    <NavLink
                      href="/migration-assistant"
                      interactive="plain"
                      className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-accent"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      AI Migration Assistant
                    </NavLink>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setUpgradeOpen(true)}
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      AI Migration Assistant
                    </Button>
                  )}
                </span>
              </div>
              {!hasPythonUpgradeCatalog(repo.data) ? (
                <p className="pt-2 text-xs text-muted-foreground">
                  Upgrade impact uses repository usage plus release evidence for every supported
                  ecosystem. The Python catalog adds extra deterministic API rules; other
                  languages fill remaining categories with AI when your plan includes it.
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}

      {unsupported ? <SupportedFeaturesPreview language={classificationLanguage(repo.data)} /> : null}

      {unsupported ? (
        <Card className="mb-6">
          <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-medium text-foreground">
                Want updates when {classificationLanguage(repo.data)} analysis ships?
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Follow the public roadmap for ecosystem support — no fabricated release dates.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href="/roadmap"
                className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
              >
                View Roadmap <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-4 text-sm font-medium text-foreground transition hover:bg-accent"
              >
                Contact us
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!unsupported && graph.data ? (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              Dependency graph
            </CardTitle>
            <CardDescription>
              Persisted edges from lockfile analysis — {graph.data.node_count} packages,{" "}
              {graph.data.edge_count} edges
            </CardDescription>
          </CardHeader>
          <CardContent>
            {graph.data.edge_count === 0 ? (
              <p className="text-sm text-muted-foreground">
                No graph edges yet. Lockfile scans populate transitive edges; re-sync
                after adding a lockfile.
              </p>
            ) : (
              <div className="max-h-64 space-y-1 overflow-y-auto text-xs">
                {graph.data.edges.slice(0, 40).map((e) => {
                  const parent = graph.data.nodes.find((n) => n.id === e.parent_dependency_id);
                  const child = graph.data.nodes.find((n) => n.id === e.child_dependency_id);
                  return (
                    <div
                      key={e.id}
                      className="flex flex-wrap items-center gap-2 rounded-md border border-border/50 px-2 py-1.5 font-mono"
                    >
                      <span>{parent?.package_name || e.parent_dependency_id.slice(0, 8)}</span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span>{child?.package_name || e.child_dependency_id.slice(0, 8)}</span>
                      {e.source ? (
                        <span className="text-muted-foreground">({e.source})</span>
                      ) : null}
                    </div>
                  );
                })}
                {graph.data.edge_count > 40 ? (
                  <p className="pt-1 text-muted-foreground">
                    Showing 40 of {graph.data.edge_count} edges
                  </p>
                ) : null}
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Dependencies</CardTitle>
          {unsupported ? (
            <CardDescription>
              Dependency inventory is reserved for supported ecosystems.
            </CardDescription>
          ) : null}
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {unsupported ? (
            <p className="py-6 text-sm text-muted-foreground">
              Verspect understood this repository. Full dependency analysis will appear here when{" "}
              {classificationLanguage(repo.data)} support is available.
            </p>
          ) : deps.isLoading && !deps.data ? (
            <div className="space-y-2 py-2">
              <LoadingCopy>Loading dependency analysis…</LoadingCopy>
              <ListSkeleton rows={6} />
            </div>
          ) : deps.isError && !deps.data ? (
            <ErrorState
              title="Unable to load dependencies"
              description={(deps.error as Error)?.message || "Try again in a moment."}
              onRetry={() => deps.refetch()}
            />
          ) : (
            <>
              <RefetchBar
                active={deps.isFetching && !deps.isLoading}
                label="Updating dependencies…"
              />
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-border text-xs text-muted-foreground">
                  <tr>
                    <th className="pb-2 font-medium">Package</th>
                    <th className="pb-2 font-medium">Current</th>
                    <th className="pb-2 font-medium">Latest</th>
                    <th className="pb-2 font-medium">Health</th>
                    <th className="pb-2 font-medium">License</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Usage</th>
                    <th className="pb-2 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((d) => (
                    <tr key={d.id} className="border-b border-border/40 hover:bg-accent/30">
                      <td className="py-3">
                        <NavLink
                          href={`/dependencies/${d.id}`}
                          interactive="plain"
                          className="font-medium text-primary hover:underline"
                        >
                          {d.package_name}
                        </NavLink>
                        <div className="text-xs text-muted-foreground">{d.file_count} files</div>
                      </td>
                      <td className="py-3 font-mono text-xs">
                        {d.current_version || (
                          <span
                            className="text-muted-foreground"
                            title={d.version_constraint || "No version pin in manifest"}
                          >
                            unpinned
                          </span>
                        )}
                      </td>
                      <td className="py-3 font-mono text-xs">{d.latest_version || "—"}</td>
                      <td className="py-3 tabular-nums">{formatScore(d.health_score)}</td>
                      <td className="py-3 text-xs">{d.license_spdx || "—"}</td>
                      <td className="py-3">
                        <Badge className={statusBadge(d.status)}>
                          {d.status.replaceAll("_", " ")}
                        </Badge>
                      </td>
                      <td className="py-3 tabular-nums">{d.usage_count}</td>
                      <td className="py-3 tabular-nums">{formatScore(d.risk_score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {deps.data && deps.data.pages > 1 ? (
                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    Page {deps.data.page} of {deps.data.pages} ({deps.data.total} packages)
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!deps.data.has_prev}
                      onClick={() => setDepPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!deps.data.has_next}
                      onClick={() => setDepPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : null}
              {!items.length ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  {analyzable
                    ? "No dependencies yet. Sync the repository to analyze manifests and usage."
                    : "Sync the repository to classify the ecosystem and run analysis when supported."}
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </AppShell>
  );
}

function ClassificationCard({ repo }: { repo: Repository }) {
  const language = classificationLanguage(repo);
  const statusLabel = supportStatusLabel(repo);
  const analyzable = isAnalyzable(repo);
  const manifest = dependencyManifest(repo);
  const confidence = classificationConfidence(repo);

  const fields = [
    { label: "Language", value: language, icon: Layers },
    { label: "Framework", value: repo.detected_framework || "—", icon: Boxes },
    { label: "Package Manager", value: repo.package_manager || "—", icon: Package },
    { label: "Dependency Manifest", value: manifest || "—", icon: FileCode2 },
  ];

  return (
    <Card className="mb-6 border-border/80">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Repository Classification</CardTitle>
            <CardDescription>
              Verspect detected the ecosystem for this repository
            </CardDescription>
          </div>
          {statusLabel ? (
            <Badge
              className={cn(
                analyzable
                  ? "border-success/40 bg-success/10 text-success"
                  : "border-primary/25 bg-primary/10 text-primary",
              )}
            >
              {statusLabel}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {fields.map(({ label, value, icon: Icon }) => (
            <div key={label} className="rounded-xl border border-border/60 bg-secondary/20 px-4 py-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
                <Icon className="h-3.5 w-3.5 text-primary/80" />
                {label}
              </div>
              <div
                className={cn(
                  "mt-2 text-sm font-medium text-foreground",
                  label === "Dependency Manifest" || label === "Package Manager"
                    ? "font-mono"
                    : "",
                )}
              >
                {value}
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t border-border/50 pt-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">
              Support Status
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Badge
                className={cn(
                  analyzable
                    ? "border-success/40 bg-success/10 text-success"
                    : "border-border bg-secondary/40 text-foreground",
                )}
              >
                {statusLabel || "—"}
              </Badge>
            </div>
          </div>
          {confidence !== null ? (
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                Classification Confidence
              </div>
              <div className="mt-1 font-mono text-sm font-medium text-foreground">
                {confidence}%
              </div>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function SupportedFeaturesPreview({ language }: { language: string }) {
  const features = [
    { label: "Repository Scan", icon: RefreshCw },
    { label: "Dependency Analysis", icon: Package },
    { label: "Security Analysis", icon: Shield },
    { label: "Upgrade Simulator", icon: Workflow },
    { label: "AI Migration Assistant (Team)", icon: Sparkles },
  ];

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>When support becomes available</CardTitle>
        <CardDescription>
          Verspect will automatically unlock analysis for {language} repositories
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-2 sm:grid-cols-2">
          {features.map(({ label, icon: Icon }) => (
            <li
              key={label}
              className="flex items-center gap-2 rounded-lg border border-border/50 bg-secondary/15 px-3 py-2 text-sm text-foreground"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Check className="h-3.5 w-3.5" />
              </span>
              <Icon className="h-3.5 w-3.5 text-muted-foreground" />
              {label}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function InsightRow({
  label,
  value,
  href,
}: {
  label: string;
  value: string;
  href?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/40 pb-2 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      {href ? (
        <NavLink
          href={href}
          interactive="plain"
          className="text-right font-medium text-primary hover:underline"
        >
          {value}
        </NavLink>
      ) : (
        <span className="text-right font-medium">{value}</span>
      )}
    </div>
  );
}

function computeInsights(items: Dependency[], repo?: Repository | null) {
  const total = repo?.dependency_count || items.length;
  const outdatedCount = repo?.outdated_count ?? items.filter((d) => d.is_outdated).length;
  if (!total) {
    return {
      freshnessLabel: "No dependencies scanned yet",
      highestRisk: "—",
      highestRiskId: null as string | null,
      mostUsed: "—",
      mostUsedId: null as string | null,
      mostVulnerable: "—",
      mostVulnerableId: null as string | null,
      debtLabel: "—",
      recommended: [] as Dependency[],
    };
  }

  const freshnessPct = Math.round(((total - outdatedCount) / total) * 100);
  const highest = [...items].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))[0];
  const mostUsed = [...items].sort((a, b) => b.usage_count - a.usage_count)[0];
  const mostVuln = [...items].sort(
    (a, b) =>
      b.critical_vuln_count - a.critical_vuln_count ||
      b.vulnerability_count - a.vulnerability_count,
  )[0];

  const debtHours = items.reduce((sum, d) => {
    if (!d.is_outdated && !d.has_vulnerabilities) return sum;
    let h = 0.5;
    if (d.major_behind >= 1) h += 4;
    else if (d.minor_behind >= 1) h += 1.5;
    else if (d.is_outdated) h += 0.75;
    if (d.has_vulnerabilities) h += 1 + d.critical_vuln_count * 2;
    h += Math.min(3, d.usage_count * 0.05);
    return sum + h;
  }, 0);

  const recommended = [...items]
    .filter((d) => d.is_outdated || d.has_vulnerabilities)
    .sort((a, b) => {
      const score = (d: Dependency) =>
        (d.critical_vuln_count || 0) * 100 +
        (d.vulnerability_count || 0) * 20 +
        (d.major_behind || 0) * 10 +
        (d.is_outdated ? 5 : 0) +
        (d.risk_score || 0);
      return score(b) - score(a);
    })
    .slice(0, 5);

  return {
    freshnessLabel: `${freshnessPct}% of ${total} packages are on the latest known version`,
    highestRisk: highest ? `${highest.package_name} (${formatScore(highest.risk_score)})` : "—",
    highestRiskId: highest?.id || null,
    mostUsed: mostUsed ? `${mostUsed.package_name} (${mostUsed.usage_count} uses)` : "—",
    mostUsedId: mostUsed?.id || null,
    mostVulnerable:
      mostVuln && mostVuln.vulnerability_count > 0
        ? `${mostVuln.package_name} (${mostVuln.vulnerability_count} CVE)`
        : "None with known CVEs",
    mostVulnerableId: mostVuln && mostVuln.vulnerability_count > 0 ? mostVuln.id : null,
    debtLabel:
      debtHours > 0
        ? `~${Math.round(debtHours)} hours across highest-risk packages`
        : "No upgrade debt on the highest-risk set",
    recommended,
  };
}
