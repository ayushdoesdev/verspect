"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  CheckCircle2,
  ChevronDown,
  CircleOff,
  ChevronRight,
  ExternalLink,
  FlaskConical,
  BookOpen,
  RefreshCw,
  Shield,
  Timer,
  AlertTriangle,
  Lock,
  Sparkles,
  Wrench,
} from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { cn, formatScore, severityColor } from "@/lib/utils";
import { useJobs } from "@/lib/jobs/jobs-context";
import { simulationTimeline } from "@/lib/jobs/stages";
import { ActivityTimeline, ProgressBar, formatElapsed } from "@/components/loading/activity-timeline";
import { AiSectionSkeleton } from "@/components/loading/skeletons";
import { LoadingButton } from "@/components/loading/loading-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MigrationAssistant } from "@/components/dependencies/migration-assistant";
import {
  getAssistantAvailabilityMessage,
  getSimulationLifecycleState,
  resolveActiveSimulationId,
  formatImpactLimitations,
  UPGRADE_ANALYSIS_SECTIONS,
  isStaleIntelligenceSimulation,
  resolveSuggestedChangeStatus,
  analysisSourceLabel,
  type SuggestedChangeStatus,
} from "@/lib/upgrade-simulator";
import {
  MigrationAssistantLockedCard,
  PremiumBadge,
  PremiumUpgradeModal,
} from "@/components/billing/premium-gate";
import { migrationReferences } from "@/lib/migration-assistant";
import { useEntitlements } from "@/lib/entitlements";
import type { DynamicUpgradeIntelligence, UpgradeSimulation } from "@/types";

type Tab =
  | "overview"
  | "analysis"
  | "breaking"
  | "files"
  | "plan"
  | "suggestions"
  | "rules"
  | "references"
  | "assistant";

const IN_PROGRESS = new Set([
  "pending",
  "queued",
  "collecting_sources",
  "analyzing_impact",
  "generating_plan",
  "scoring",
  "preparing",
  "detecting_api",
  "matching_rules",
  "filling_categories",
  "building_plan",
  "generating_suggestions",
  "ai_migration_assistant",
  "calculating_confidence",
]);

export function UpgradeSimulator({
  dependencyId,
  currentVersion,
  latestVersion,
  packageName,
  readOnlyReason,
}: {
  dependencyId: string;
  currentVersion?: string | null;
  latestVersion?: string | null;
  packageName: string;
  /** When set, new simulations are blocked (e.g. archived repository). History stays viewable. */
  readOnlyReason?: string | null;
}) {
  const qc = useQueryClient();
  const { trackSimulation, toast, cancelJobSimulation, retryJobSimulation, workerStatus } =
    useJobs();
  const entitlements = useEntitlements();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("analysis");
  const [expandedFiles, setExpandedFiles] = useState<Record<string, boolean>>({});
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [teamUpgradeOpen, setTeamUpgradeOpen] = useState(false);
  const [lastTriggerKey, setLastTriggerKey] = useState<string | null>(null);
  const [uiStatusOverride, setUiStatusOverride] = useState<string | null>(null);

  // Upgrade Simulator = Free+ (analysis)
  const canSimulate = entitlements.upgradeSimulator;
  const simulatorLocked = !entitlements.loading && !canSimulate;
  // AI Migration Assistant = Team+ (code generation)
  const canMigration = entitlements.canGenerateAiMigration;
  const migrationLocked = !entitlements.loading && !canMigration;

  const list = useQuery({
    queryKey: ["simulations", dependencyId],
    queryFn: () => api.listSimulations(dependencyId),
  });

  useEffect(() => {
    if (activeId) return;

    const storedId = window.sessionStorage.getItem(`simulator-active-${dependencyId}`);
    const nextId = resolveActiveSimulationId({
      activeId,
      storedId,
      simulations: list.data,
    });

    if (nextId && nextId !== activeId) {
      setActiveId(nextId);
    }
  }, [activeId, dependencyId, list.data]);

  useEffect(() => {
    if (activeId) {
      window.sessionStorage.setItem(`simulator-active-${dependencyId}`, activeId);
    }
  }, [activeId, dependencyId]);

  const simQuery = useQuery({
    queryKey: ["simulation", dependencyId, activeId],
    queryFn: () => api.getSimulation(dependencyId, activeId!),
    enabled: !!activeId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status && IN_PROGRESS.has(status) ? 2000 : false;
    },
  });

  // Drop optimistic cancelled override once the server status is authoritative.
  useEffect(() => {
    const status = simQuery.data?.status;
    if (!uiStatusOverride || !status) return;
    if (status === "cancelled" || status === "completed" || status === "failed") {
      setUiStatusOverride(null);
    }
  }, [simQuery.data?.status, uiStatusOverride]);

  const start = useMutation({
    mutationFn: (force: boolean) =>
      api.simulateUpgrade(dependencyId, {
        target_version: latestVersion || undefined,
        force_refresh: force,
      }),
    onSuccess: (data) => {
      setActiveId(data.id);
      trackSimulation(data.id, dependencyId, {
        title: "Upgrade Simulation",
        subtitle: `${packageName} ${currentVersion || "?"} → ${latestVersion || "?"}`,
        showModal: false,
      });
      qc.invalidateQueries({ queryKey: ["simulations", dependencyId] });
      qc.invalidateQueries({ queryKey: ["simulation", dependencyId, data.id] });
      qc.invalidateQueries({ queryKey: ["subscription"] });
      qc.invalidateQueries({ queryKey: ["usage"] });
    },
    onError: (err) => {
      if (err instanceof ApiError && (err.status === 403 || err.status === 402)) {
        setUpgradeOpen(true);
        toast("Plan limit reached", {
          tone: "error",
          description: err.detail || "Unable to start Upgrade Simulator on your current plan.",
          actionLabel: "View plans",
        });
        return;
      }
      toast("Simulation unavailable", {
        tone: "error",
        description: (err as Error).message || "Unable to start simulation",
        actionLabel: "Retry",
      });
    },
  });

  const quickImpact = useMutation({
    mutationFn: () =>
      api.analyzeUpgradeImpact(dependencyId, {
        target_version: latestVersion || undefined,
      }),
    onError: (err) => {
      if (err instanceof ApiError && (err.status === 403 || err.status === 402)) {
        setUpgradeOpen(true);
        return;
      }
      toast("Impact analysis failed", {
        tone: "error",
        description: (err as Error).message || "Unable to analyze upgrade impact",
      });
    },
  });

  const refresh = useMutation({
    mutationFn: () => api.refreshSimulation(dependencyId, activeId!),
    onSuccess: (data) => {
      setActiveId(data.id);
      trackSimulation(data.id, dependencyId, {
        title: "Upgrade Simulation",
        subtitle: `${packageName} refresh`,
        showModal: false,
      });
      qc.invalidateQueries({ queryKey: ["simulations", dependencyId] });
      qc.invalidateQueries({ queryKey: ["subscription"] });
      qc.invalidateQueries({ queryKey: ["usage"] });
    },
    onError: (err) => {
      if (err instanceof ApiError && (err.status === 403 || err.status === 402)) {
        setUpgradeOpen(true);
      }
    },
  });

  const sim = simQuery.data;
  const effectiveStatus = uiStatusOverride || sim?.status;
  const effectiveSim = useMemo(
    () => (sim ? { ...sim, status: effectiveStatus || sim.status } : sim),
    [effectiveStatus, sim],
  );
  const running = !!(effectiveSim && IN_PROGRESS.has(effectiveSim.status)) || start.isPending;
  const hasExistingReport = !!(list.data?.length || (effectiveSim && effectiveSim.status === "completed"));

  const lifecycle = useMemo(
    () =>
      getSimulationLifecycleState({
        status: effectiveSim?.status,
        startedAt: effectiveSim?.started_at,
        progress: effectiveSim?.progress_percent,
        errorMessage: effectiveSim?.error_message,
      }),
    [effectiveSim?.error_message, effectiveSim?.progress_percent, effectiveSim?.started_at, effectiveSim?.status],
  );
  const elapsedMs = useMemo(() => {
    if (!effectiveSim?.started_at) return null;
    const started = Date.parse(effectiveSim.started_at);
    if (!Number.isFinite(started)) return null;
    return Date.now() - started;
  }, [effectiveSim?.started_at]);

  function requestGenerate(force = false) {
    if (simulatorLocked) {
      setUpgradeOpen(true);
      return;
    }
    const triggerKey = `${dependencyId}:${latestVersion || ""}`;
    if (!force && lastTriggerKey === triggerKey && running) {
      toast("Simulation already in progress", {
        tone: "info",
        description: "This repository and target version already has an active run.",
      });
      return;
    }
    start.mutate(force);
    setLastTriggerKey(triggerKey);
  }

  async function cancelSimulation() {
    if (!effectiveSim?.id) return;
    try {
      await cancelJobSimulation(dependencyId, effectiveSim.id);
      // Only sticky-cancel after the backend accepts the cancel request.
      setUiStatusOverride("cancelled");
    } catch {
      setUiStatusOverride(null);
    }
    qc.invalidateQueries({ queryKey: ["simulation", dependencyId, effectiveSim.id] });
    qc.invalidateQueries({ queryKey: ["simulations", dependencyId] });
  }

  async function retrySimulation() {
    if (!effectiveSim?.id) return;
    setUiStatusOverride(null);
    await retryJobSimulation(dependencyId, effectiveSim.id);
    qc.invalidateQueries({ queryKey: ["simulation", dependencyId, effectiveSim.id] });
    qc.invalidateQueries({ queryKey: ["simulations", dependencyId] });
  }

  const tabs: Array<[Tab, string, boolean?]> = [
    ["overview", "Overview"],
    ["analysis", "Analysis"],
    ["breaking", "Breaking Changes"],
    ["files", "Affected Files"],
    ["plan", "Timeline"],
    ["suggestions", "Suggested Patches"],
    ["rules", "Migration Rules"],
    ["references", "Official References"],
    ["assistant", "AI Migration Assistant", true],
  ];

  const assistantMessage = getAssistantAvailabilityMessage({
    simCompleted: effectiveSim?.status === "completed",
    migrationLocked,
    canMigration,
  });

  return (
    <Card className="mb-6 overflow-hidden border-primary/20">
      <PremiumUpgradeModal
        open={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        variant={entitlements.evaluationExpired ? "evaluation" : "starter"}
      />
      <PremiumUpgradeModal
        open={teamUpgradeOpen}
        onClose={() => setTeamUpgradeOpen(false)}
        variant="team"
      />
      <CardHeader className="flex flex-col gap-3 border-b border-border/60 bg-primary/5 sm:flex-row sm:items-center sm:justify-between">
        <div className="max-w-2xl">
          <div className="mb-1 flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            <CardTitle>Upgrade Simulator</CardTitle>
            {simulatorLocked ? <PremiumBadge variant="locked" /> : null}
          </div>
          <CardDescription>
            Analysis-only upgrade impact for{" "}
            <span className="font-mono text-foreground">
              {packageName} {currentVersion || "unpinned"} → {latestVersion || "?"}
            </span>
            . Available on every plan. Code patches require AI Migration Assistant (Team+).
          </CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          {sim?.status === "completed" && activeId && canSimulate && !readOnlyReason ? (
            <LoadingButton
              variant="outline"
              size="sm"
              loading={refresh.isPending}
              loadingText="Refreshing…"
              disabled={running}
              onClick={() => refresh.mutate()}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh analysis
            </LoadingButton>
          ) : null}
          <span title={readOnlyReason || undefined}>
            <LoadingButton
              variant="outline"
              size="sm"
              loading={quickImpact.isPending}
              loadingText="Analyzing…"
              disabled={!latestVersion || !!readOnlyReason || simulatorLocked}
              onClick={() => {
                if (readOnlyReason || simulatorLocked) {
                  if (simulatorLocked) setUpgradeOpen(true);
                  return;
                }
                quickImpact.mutate();
              }}
            >
              <Shield className="h-4 w-4" />
              Analyze impact
            </LoadingButton>
          </span>
          <span title={readOnlyReason || undefined}>
            <LoadingButton
              size="sm"
              loading={canSimulate && (start.isPending || (!!sim && IN_PROGRESS.has(sim.status)))}
              loadingText="Simulating…"
              disabled={!latestVersion || !!readOnlyReason}
              onClick={() => {
                if (readOnlyReason) return;
                requestGenerate(false);
              }}
            >
              <FlaskConical className="h-4 w-4" />
              {simulatorLocked ? "Unlock simulator" : "Run simulation"}
            </LoadingButton>
          </span>
        </div>
      </CardHeader>

      <CardContent className="p-5">
        {readOnlyReason ? (
          <p className="mb-4 rounded-md border border-border/60 bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            {readOnlyReason}
          </p>
        ) : null}
        {simulatorLocked && !hasExistingReport ? (
          <div className="rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/10 via-card to-transparent p-6">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">Upgrade Simulator unavailable</span>
            </div>
            <p className="max-w-2xl text-sm text-muted-foreground">
              {entitlements.evaluationExpired
                ? "Your evaluation has ended. Previous simulation reports remain visible. Upgrade to Starter or higher to run new analyses."
                : "Upgrade Simulator analysis is included during evaluation and on all paid plans. Upgrade to restore access."}
            </p>
            <Button className="mt-4" onClick={() => setUpgradeOpen(true)}>
              {entitlements.evaluationExpired ? "Upgrade to continue" : "View plans"}
            </Button>
          </div>
        ) : null}

        {simulatorLocked && hasExistingReport ? (
          <div className="mb-4 rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 text-sm">
            <div className="font-medium text-warning">New simulations are currently locked</div>
            <p className="mt-1 text-muted-foreground">
              Existing reports stay available for review. Refresh entitlements or upgrade your plan
              to generate a fresh analysis.
            </p>
            <Button size="sm" className="mt-3" onClick={() => setUpgradeOpen(true)}>
              View plans
            </Button>
          </div>
        ) : null}

        {!latestVersion ? (
          <p className="text-sm text-muted-foreground">
            No latest version known yet. Run a repository scan first.
          </p>
        ) : null}

        {start.isError && !simulatorLocked ? (
          <p className="mb-3 text-sm text-destructive">
            {(start.error as Error).message || "Failed to start simulation"}
          </p>
        ) : null}

        {quickImpact.data ? (
          <div className="mb-5 rounded-xl border border-border/60 bg-background/40 p-4 animate-fade-up">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Shield className="h-4 w-4 text-primary" />
              <div className="text-sm font-semibold">Deterministic upgrade impact</div>
              <Badge className="border-border text-muted-foreground">
                {quickImpact.data.analysis_source}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {Math.round((quickImpact.data.confidence || 0) * 100)}% confidence
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{quickImpact.data.summary}</p>
            <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-4">
              <div>
                Breaking:{" "}
                <span className="font-medium text-foreground">
                  {quickImpact.data.breaking_findings?.length || 0}
                </span>
              </div>
              <div>
                Unresolved APIs:{" "}
                <span className="font-medium text-foreground">
                  {quickImpact.data.unresolved_apis?.length || 0}
                </span>
              </div>
              <div>
                Used APIs:{" "}
                <span className="font-medium text-foreground">
                  {quickImpact.data.used_apis?.length || 0}
                </span>
              </div>
              <div>
                Catalog rules:{" "}
                <span className="font-medium text-foreground">
                  {quickImpact.data.catalog_rules_applied || 0}
                </span>
              </div>
            </div>
            {(quickImpact.data.breaking_findings || []).length > 0 ? (
              <ul className="mt-3 space-y-2 border-t border-border/40 pt-3">
                {quickImpact.data.breaking_findings.slice(0, 5).map((f, i) => (
                  <li key={i} className="rounded-md border border-destructive/20 bg-destructive/5 p-2">
                    <div className="font-mono text-sm">{f.affected_api}</div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{f.description}</p>
                    {(f.evidence || []).slice(0, 3).map((e, ei) => (
                      <p key={ei} className="mt-1 font-mono text-[11px] text-muted-foreground">
                        {e.file_path}
                        {e.line != null ? `:${e.line}` : ""}
                      </p>
                    ))}
                  </li>
                ))}
              </ul>
            ) : null}
            {(quickImpact.data.unresolved_apis || []).length > 0 ? (
              <p className="mt-3 text-xs text-muted-foreground">
                Unresolved (no deterministic rule):{" "}
                {quickImpact.data.unresolved_apis.slice(0, 8).join(", ")}
                {quickImpact.data.unresolved_apis.length > 8 ? "…" : ""}
              </p>
            ) : null}
            {(formatImpactLimitations(quickImpact.data.analysis_limitations).length > 0) ? (
              <ul className="mt-3 space-y-1 border-t border-border/40 pt-3 text-xs text-muted-foreground">
                {formatImpactLimitations(quickImpact.data.analysis_limitations).map((limit, i) => (
                  <li key={i}>Limitation: {limit}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {running && canSimulate && !effectiveSim ? <AiSectionSkeleton /> : null}

        {running && canSimulate && effectiveSim ? (
          <div className="mb-5 animate-fade-up rounded-xl border border-border/60 bg-background/40 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <span>Gathering upgrade insight</span>
                {elapsedMs != null ? <span className="tabular-nums">Elapsed {formatElapsed(elapsedMs)}</span> : null}
              </div>
              <span className="tabular-nums">{effectiveSim.progress_percent}%</span>
            </div>
            <ProgressBar value={effectiveSim.progress_percent} className="mb-4" />
            {workerStatus && !workerStatus.online ? (
              <p className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
                Worker Offline — background processing service is unavailable. The simulation
                resumes automatically once a worker reconnects.
              </p>
            ) : null}
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" onClick={cancelSimulation}>
                <CircleOff className="mr-1 h-3.5 w-3.5" />
                Cancel simulation
              </Button>
              <Button size="sm" variant="ghost" onClick={retrySimulation}>
                <RefreshCw className="mr-1 h-3.5 w-3.5" />
                Retry
              </Button>
              <span className="text-xs text-muted-foreground">You can leave this page and keep monitoring progress.</span>
            </div>
            <ActivityTimeline
              steps={simulationTimeline(
                effectiveSim.current_stage,
                effectiveSim.progress_percent,
                effectiveSim.status,
                { lockAiMigrationAssistant: migrationLocked },
              )}
              compact
            />
          </div>
        ) : null}

        {effectiveSim?.status === "failed" || effectiveSim?.status === "cancelled" || lifecycle.state === "timed_out" ? (
          <div className="mb-4 rounded-2xl border border-border/60 bg-background/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  {lifecycle.state === "timed_out" ? <Timer className="h-4 w-4 text-warning" /> : lifecycle.state === "cancelled" ? <CircleOff className="h-4 w-4 text-muted-foreground" /> : <AlertTriangle className="h-4 w-4 text-destructive" />}
                  {lifecycle.title}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{lifecycle.detail}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => requestGenerate(true)}>
                {lifecycle.actionLabel}
              </Button>
            </div>
          </div>
        ) : null}

        {effectiveSim?.status === "completed" ? (
          <>
            <OverviewCards sim={effectiveSim} />

            {isStaleIntelligenceSimulation(effectiveSim) ? (
              <div className="mb-5 rounded-2xl border border-warning/40 bg-warning/10 p-4">
                <div className="text-sm font-semibold text-foreground">
                  Re-run required for Dynamic Upgrade Intelligence
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  This saved report was generated before the current analysis engine. It is kept
                  for history and is not reinterpreted as AI-assisted intelligence. Refresh to run
                  a fresh analysis.
                </p>
                {canSimulate && !readOnlyReason ? (
                  <Button size="sm" className="mt-3" onClick={() => refresh.mutate()}>
                    <RefreshCw className="mr-1 h-3.5 w-3.5" />
                    Refresh analysis
                  </Button>
                ) : null}
              </div>
            ) : null}

            {assistantMessage ? (
              <div className="mb-5 rounded-2xl border border-border/60 bg-background/45 p-4">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="rounded-xl border border-primary/25 bg-primary/10 p-2 text-primary">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-semibold">{assistantMessage.title}</div>
                    <p className="mt-1 text-sm text-muted-foreground">{assistantMessage.detail}</p>
                    {assistantMessage.ctaLabel ? (
                      <Button size="sm" className="mt-3" onClick={() => setTeamUpgradeOpen(true)}>
                        {assistantMessage.ctaLabel}
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}

            <div className="mb-4 mt-6 flex flex-wrap gap-1 border-b border-border/60 pb-2">
              {tabs.map(([id, label, locked]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    tab === id
                      ? "bg-primary/15 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  {label}
                  {locked && migrationLocked ? (
                    <Lock className="h-3 w-3 opacity-70" aria-label="Team exclusive" />
                  ) : null}
                </button>
              ))}
            </div>

            {tab === "overview" ? <OverviewTab sim={effectiveSim} /> : null}
            {tab === "analysis" ? <AnalysisTab sim={effectiveSim} /> : null}
            {tab === "breaking" ? <BreakingTab sim={effectiveSim} /> : null}
            {tab === "files" ? (
              <FilesTab
                sim={effectiveSim}
                expanded={expandedFiles}
                setExpanded={setExpandedFiles}
                suggestions={effectiveSim.suggested_changes || []}
              />
            ) : null}
            {tab === "plan" ? <PlanTab sim={effectiveSim} /> : null}
            {tab === "suggestions" ? <SuggestionsTab sim={effectiveSim} /> : null}
            {tab === "rules" ? <RulesTab sim={effectiveSim} /> : null}
            {tab === "references" ? <ReferencesTab sim={effectiveSim} /> : null}
            {tab === "assistant" ? (
              <div className="space-y-4 animate-fade-up">
                <div className="rounded-2xl border border-border/70 bg-gradient-to-br from-primary/10 via-card/80 to-transparent p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-primary">
                        <Sparkles className="h-3.5 w-3.5" />
                        AI Migration Assistant
                      </div>
                      <h3 className="text-base font-semibold tracking-tight">Line-by-line migration guidance for the work that matters</h3>
                      <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                        This companion experience helps you move from inventory to action with exact code replacements, implementation guidance, and patch-ready recommendations for your repository.
                      </p>
                    </div>
                    {migrationLocked ? (
                      <PremiumBadge variant="team" />
                    ) : (
                      <Badge className="border-success/40 bg-success/10 text-success">Available</Badge>
                    )}
                  </div>
                  <div className="mt-4 grid gap-2 md:grid-cols-2">
                    {[
                      "Exact code replacements",
                      "Line-by-line migration guidance",
                      "Patch generation",
                      "Breaking change explanations",
                      "Implementation guidance",
                    ].map((item) => (
                      <div key={item} className="rounded-xl border border-border/60 bg-background/40 px-3 py-2 text-sm text-muted-foreground">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                {migrationLocked ? (
                  <div className="space-y-4">
                    <MigrationAssistantLockedCard onUpgrade={() => setTeamUpgradeOpen(true)} />
                    <p className="text-center text-xs text-muted-foreground">
                      Deterministic analysis completed successfully. Your plan currently limits AI patch generation and detailed migration assistance.
                    </p>
                  </div>
                ) : (
                  <MigrationAssistant sim={effectiveSim} />
                )}
              </div>
            ) : null}
          </>
        ) : null}

        {!sim && !running && latestVersion && canSimulate ? (
          <div className="rounded-2xl border border-border/60 bg-background/40 p-5 text-sm text-muted-foreground">
            <div className="font-medium text-foreground">Ready when you are</div>
            <p className="mt-1">
              Run a simulation to review breaking changes, upgrade readiness, and migration guidance in a single view. Team and Enterprise plans unlock the AI Migration Assistant for exact code replacements and patch generation.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function OverviewCards({ sim }: { sim: UpgradeSimulation }) {
  const auto =
    sim.readiness_factors?.auto_fix_count ??
    sim.automatic_fixes_possible?.length ??
    0;
  const manual =
    sim.readiness_factors?.manual_fix_count ??
    sim.manual_work_required?.length ??
    0;

  const items = [
    {
      label: "Upgrade readiness",
      value: formatScore(sim.readiness_score),
      icon: CheckCircle2,
      tone: "text-primary",
    },
    {
      label: "Risk level",
      value: formatScore(sim.risk_score),
      icon: AlertTriangle,
      tone: "text-warning",
    },
    {
      label: "Estimated effort",
      value: sim.migration_time_label || "—",
      icon: Timer,
      tone: "text-chart-2",
    },
    {
      label: "Static analysis",
      value: sim.confidence != null ? `${Math.round(sim.confidence * 100)}%` : "—",
      icon: FlaskConical,
      tone: "text-foreground",
    },
    {
      label: "Security improvements",
      value: sim.security_improvements?.length ? `${sim.security_improvements.length}` : "0",
      icon: Sparkles,
      tone: "text-success",
    },
    {
      label: "Auto-fix opportunities",
      value: `${auto} / ${manual}`,
      icon: Wrench,
      tone: "text-chart-3",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.label}
            className="rounded-lg border border-border/70 bg-card/60 p-3 animate-fade-up"
          >
            <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon className={cn("h-3.5 w-3.5", item.tone)} />
              {item.label}
            </div>
            <div className="text-lg font-semibold tabular-nums">{item.value}</div>
          </div>
        );
      })}
    </div>
  );
}

function intelligenceOf(sim: UpgradeSimulation): DynamicUpgradeIntelligence | null {
  if (sim.dynamic_intelligence) return sim.dynamic_intelligence;
  const raw = sim.collected_sources?.dynamic_intelligence;
  if (raw && typeof raw === "object") return raw as DynamicUpgradeIntelligence;
  return null;
}

function methodLabel(method?: string | null): string {
  if (method === "deterministic+ai") return "Deterministic + AI";
  if (method === "ai") return "AI";
  return "Deterministic";
}

function classificationLabel(value?: string | null): string {
  switch (value) {
    case "safe":
      return "Safe / no impact detected";
    case "low_risk":
      return "Low risk";
    case "potentially_breaking":
      return "Potentially breaking";
    case "breaking":
      return "Breaking";
    default:
      return "Unresolved";
  }
}

function OverviewTab({ sim }: { sim: UpgradeSimulation }) {
  const intel = intelligenceOf(sim);
  const factorEntries = Object.entries(sim.readiness_factors || {}).filter(
    ([, v]) => typeof v === "number" && Number(v) <= 100,
  );
  const classification = intel?.breaking_classification || sim.breaking_classification;
  const method = intel?.analysis_method || sim.analysis_method;

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          className={
            classification === "breaking"
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : classification === "potentially_breaking"
                ? "border-warning/40 bg-warning/10 text-warning"
                : classification === "safe" || sim.safe_to_upgrade
                  ? "border-success/40 bg-success/10 text-success"
                  : "border-warning/40 bg-warning/10 text-warning"
          }
        >
          {classification ? classificationLabel(classification) : sim.safe_to_upgrade ? "Ready for upgrade" : "Needs migration work"}
        </Badge>
        {method ? (
          <Badge className="border-border text-muted-foreground">{methodLabel(method)}</Badge>
        ) : null}
        <Badge className="border-border font-mono text-muted-foreground">
          {sim.from_version} → {sim.to_version}
        </Badge>
        {sim.model_used ? (
          <Badge className="border-border text-muted-foreground">Analysis engine: {sim.model_used}</Badge>
        ) : null}
        {sim.confidence != null ? (
          <Badge className="border-border text-muted-foreground">
            Static analysis {sim.confidence >= 0.75 ? "strong" : sim.confidence >= 0.45 ? "moderate" : "limited"}
          </Badge>
        ) : null}
        {sim.engine_report_id ? (
          <Badge className="border-border font-mono text-muted-foreground">
            report {sim.engine_report_id.slice(0, 8)}
          </Badge>
        ) : null}
      </div>
      <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
        <p className="text-sm leading-relaxed text-muted-foreground">{sim.summary}</p>
        {(intel?.ai_skipped_reason === "plan_does_not_include_ai" || sim.ai_skipped_reason === "plan_does_not_include_ai") ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Additional AI analysis requires a plan that includes AI (Pro, Team, or Enterprise).
            Deterministic findings are shown.
          </p>
        ) : null}
        {(intel?.degradation || []).includes("ai_timeout") || intel?.ai_skipped_reason === "ai_timeout" ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Partial analysis available. AI-assisted analysis timed out.
          </p>
        ) : (intel?.degradation || []).includes("ai_unavailable") ||
          (intel?.degradation || []).includes("ai_completion_failed") ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Partial analysis available. AI completion is currently unavailable.
          </p>
        ) : (intel?.degradation || []).includes("malformed_ai_response") ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Partial analysis available. AI output could not be validated.
          </p>
        ) : null}
      </div>

      {factorEntries.length ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {factorEntries.map(([k, v]) => (
            <div key={k} className="rounded-md border border-border/50 p-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {k.replaceAll("_", " ")}
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.min(100, Number(v))}%` }}
                />
              </div>
              <div className="mt-1 text-xs tabular-nums">{formatScore(Number(v))}</div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <ListBlock title="Security improvements" items={sim.security_improvements || []} />
        <ListBlock title="Performance improvements" items={sim.performance_improvements || []} />
        <ListBlock title="Manual migration work" items={sim.manual_work_required || []} />
        <ListBlock title="Auto-fix opportunities" items={sim.automatic_fixes_possible || []} />
      </div>
    </div>
  );
}

function AnalysisTab({ sim }: { sim: UpgradeSimulation }) {
  const intel = intelligenceOf(sim);
  const categories = intel?.categories || {};
  const order: Array<[(typeof UPGRADE_ANALYSIS_SECTIONS)[number], string[]]> = [
    ["Summary", ["recommended_target_version", "migration_required", "upgrade_appears_safe", "upgrade_potentially_breaking", "upgrade_verified_breaking"]],
    ["What Changed", ["what_changed", "removed_apis", "renamed_apis", "changed_apis", "changed_signatures", "changed_types", "changed_modules", "changed_defaults", "deprecated_functionality"]],
    ["Breaking Changes", ["breaking_changes"]],
    ["Affected APIs", ["affected_apis_used"]],
    ["Affected Files", ["affected_files", "affected_lines", "why_file_affected"]],
    ["Required Changes", ["required_code_changes"]],
    ["Configuration Changes", ["changed_configuration", "required_configuration_changes"]],
    ["Migration Rules", ["migration_rules", "migration_steps"]],
    ["Security Impact", ["security_relevant_changes"]],
    ["Risk", ["upgrade_risk"]],
    ["Confidence", ["confidence"]],
    ["Evidence", ["evidence"]],
    ["Sources", ["sources", "affected_dependencies"]],
    ["Migration Plan", []],
  ];

  if (!intel) {
    return (
      <p className="animate-fade-up text-sm text-muted-foreground">
        Category-level upgrade intelligence is not attached to this report. Re-run the simulation to
        generate per-category analysis.
      </p>
    );
  }

  return (
    <div className="space-y-5 animate-fade-up">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge className="border-border text-muted-foreground">
          {classificationLabel(intel.breaking_classification)}
        </Badge>
        <Badge className="border-border text-muted-foreground">{methodLabel(intel.analysis_method)}</Badge>
        {intel.ai_invoked ? (
          <Badge className="border-border text-muted-foreground">AI invoked</Badge>
        ) : (
          <Badge className="border-border text-muted-foreground">AI not invoked</Badge>
        )}
      </div>
      {order.map(([title, ids]) => (
        <section key={title} className="space-y-2">
          <h4 className="text-sm font-medium">{title}</h4>
          {title === "Summary" && intel.summary ? (
            <p className="text-sm text-muted-foreground">{intel.summary}</p>
          ) : null}
          {title === "Migration Plan" ? (
            (sim.migration_plan || []).length ? (
              <div className="space-y-2">
                {(sim.migration_plan || []).map((p) => (
                  <div key={p.phase} className="rounded-md border border-border/70 p-3">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">{p.title}</span>
                      <Badge className="border-border text-muted-foreground">{p.difficulty}</Badge>
                    </div>
                    {p.description ? (
                      <p className="mt-1 text-sm text-muted-foreground">{p.description}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No migration plan is attached to this report.
              </p>
            )
          ) : null}
          {ids.map((id) => {
            const cat = categories[id];
            if (!cat) return null;
            return (
              <div key={id} className="rounded-md border border-border/70 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{cat.title}</span>
                  <Badge className="border-border text-muted-foreground">
                    {methodLabel(cat.analysis_method)}
                  </Badge>
                  {cat.claim_status ? (
                    <Badge className="border-border text-muted-foreground">{cat.claim_status}</Badge>
                  ) : null}
                  {cat.completeness ? (
                    <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      {cat.completeness}
                    </span>
                  ) : null}
                </div>
                {cat.answer ? (
                  <p className="mt-1 text-sm text-muted-foreground">{cat.answer}</p>
                ) : null}
                {(cat.findings || []).slice(0, 6).map((f, i) => (
                  <div key={i} className="mt-2 border-t border-border/40 pt-2 text-xs">
                    <div className="font-mono text-foreground">{f.finding}</div>
                    {f.explanation ? <p className="mt-0.5 text-muted-foreground">{f.explanation}</p> : null}
                    {f.required_change ? (
                      <p className="mt-0.5 text-primary">{f.required_change}</p>
                    ) : null}
                    {(f.affected_files || []).slice(0, 4).map((loc, li) => (
                      <p key={li} className="mt-0.5 font-mono text-muted-foreground">
                        {loc.file}
                        {loc.line != null ? `:${loc.line}` : ""}
                        {loc.api ? ` · ${loc.api}` : ""}
                        {loc.usage_kind ? ` · ${loc.usage_kind}` : ""}
                      </p>
                    ))}
                  </div>
                ))}
                {(cat.gaps || []).length ? (
                  <p className="mt-2 text-xs text-muted-foreground">Gap: {cat.gaps![0]}</p>
                ) : null}
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}

function BreakingTab({ sim }: { sim: UpgradeSimulation }) {
  return (
    <div className="space-y-4 animate-fade-up">
      <section>
        <h4 className="mb-2 text-sm font-medium">Breaking APIs</h4>
        {(sim.breaking_apis || []).length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No breaking APIs identified against your usage. Review release notes under Official
            References for package-level changes.
          </p>
        ) : (
          <div className="space-y-2">
            {(sim.breaking_apis || []).map((b, i) => (
              <div key={i} className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm">
                    {b.fully_qualified_name || b.api || b.symbol}
                  </span>
                  {b.severity ? (
                    <span className={`text-xs uppercase ${severityColor(b.severity)}`}>
                      {b.severity}
                    </span>
                  ) : null}
                  {b.kind || b.change_type ? (
                    <Badge className="border-border text-muted-foreground">
                      {b.kind || b.change_type}
                    </Badge>
                  ) : null}
                  {b.analysis_source ? (
                    <Badge className="border-border text-muted-foreground">
                      {b.analysis_source}
                    </Badge>
                  ) : null}
                  <span className="text-xs text-muted-foreground">
                    {Math.round((b.confidence || 0) * 100)}% conf
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {b.reason || b.description || "Potential breaking change with repository evidence."}
                </p>
                {b.replacement ? (
                  <p className="mt-1 text-xs text-primary">Replace with: {b.replacement}</p>
                ) : null}
                {(b.evidence || []).length > 0 ? (
                  <ul className="mt-2 space-y-1 border-t border-border/40 pt-2 text-xs text-muted-foreground">
                    {b.evidence!.slice(0, 8).map((e, ei) => (
                      <li key={ei} className="font-mono">
                        {e.file_path}
                        {e.line != null ? `:${e.line}` : ""}
                        {e.code_snippet ? (
                          <span className="text-foreground/80"> — {e.code_snippet}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (b.affected_files || []).length > 0 ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Affected: {(b.affected_files || []).join(", ")}
                  </p>
                ) : null}
                {b.official_reference ? <OfficialLink href={b.official_reference} /> : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="mb-2 text-sm font-medium">Deprecated APIs</h4>
        {(sim.deprecated_apis || []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No deprecated APIs flagged in your usage.</p>
        ) : (
          <div className="space-y-2">
            {(sim.deprecated_apis || []).map((d, i) => (
              <div key={i} className="rounded-md border border-warning/30 bg-warning/5 p-3">
                <div className="font-mono text-sm">{d.fully_qualified_name || d.symbol}</div>
                <p className="mt-1 text-sm text-muted-foreground">{d.reason}</p>
                {d.replacement ? (
                  <p className="mt-1 text-xs text-primary">Replace with: {d.replacement}</p>
                ) : null}
                {d.official_reference ? <OfficialLink href={d.official_reference} /> : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function FilesTab({
  sim,
  expanded,
  setExpanded,
  suggestions,
}: {
  sim: UpgradeSimulation;
  expanded: Record<string, boolean>;
  setExpanded: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  suggestions: NonNullable<UpgradeSimulation["suggested_changes"]>;
}) {
  const files = sim.affected_files || [];
  if (!files.length) {
    return (
      <div className="rounded-2xl border border-border/60 bg-background/40 p-5 text-sm text-muted-foreground animate-fade-up">
        <div className="font-medium text-foreground">No affected files detected</div>
        <p className="mt-1">
          Repository analysis completed, but no usage sites were found for this dependency in the scanned source files.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="rounded-2xl border border-border/60 bg-background/40 p-4 text-sm text-muted-foreground">
        <div className="font-medium text-foreground">Affected files overview</div>
        <p className="mt-1">
          {files.length} file{files.length === 1 ? "" : "s"} surfaced from the repository analysis, with usage data grouped by API impact and migration complexity.
        </p>
      </div>
      {files.map((f) => {
        const open = !!expanded[f.file_path];
        const fileSuggestions = suggestions.filter((s) => s.file_path === f.file_path);
        const sites = (f as { usage_sites?: Array<Record<string, unknown>> }).usage_sites || [];
        return (
          <div key={f.file_path} className="rounded-2xl border border-border/70 bg-card/40">
            <button
              className="flex w-full items-center gap-2 px-3 py-3 text-left hover:bg-accent/40"
              onClick={() =>
                setExpanded((prev) => ({ ...prev, [f.file_path]: !prev[f.file_path] }))
              }
            >
              {open ? (
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <span className="min-w-0 flex-1 truncate font-mono text-sm">{f.file_path}</span>
              <div className="ml-auto flex flex-wrap items-center gap-2">
                <Badge className="border-border text-muted-foreground">
                  {f.affected_apis.length} affected usages
                </Badge>
                {sites.length ? (
                  <Badge className="border-border text-muted-foreground">{sites.length} breaking usages</Badge>
                ) : null}
                <span className="text-xs text-muted-foreground">
                  {Math.round(f.confidence * 100)}% confidence
                </span>
              </div>
            </button>
            {open ? (
              <div className="space-y-3 border-t border-border/60 px-3 py-3">
                <p className="text-sm text-muted-foreground">{f.reason}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-xl border border-border/60 bg-background/40 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Affected usages</div>
                    <div className="mt-1 text-sm font-medium text-foreground">{f.affected_apis.length}</div>
                  </div>
                  <div className="rounded-xl border border-border/60 bg-background/40 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Breaking usages</div>
                    <div className="mt-1 text-sm font-medium text-foreground">{sites.length}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  {f.affected_apis.map((apiName) => (
                    <Badge key={apiName} className="border-border font-mono text-muted-foreground">
                      {apiName}
                    </Badge>
                  ))}
                </div>
                {sites.length ? (
                  <div className="overflow-x-auto rounded border border-border/50">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-border/60 text-muted-foreground">
                        <tr>
                          <th className="px-2 py-1.5 font-medium">Symbol</th>
                          <th className="px-2 py-1.5 font-medium">Kind</th>
                          <th className="px-2 py-1.5 font-medium">Line</th>
                          <th className="px-2 py-1.5 font-medium">Context</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sites.map((s, i) => (
                          <tr key={i} className="border-b border-border/30">
                            <td className="px-2 py-1.5 font-mono">
                              {String(s.fully_qualified_name || s.symbol || "—")}
                            </td>
                            <td className="px-2 py-1.5 text-muted-foreground">
                              {String(s.usage_kind || "—")}
                            </td>
                            <td className="px-2 py-1.5 tabular-nums">{String(s.line ?? "—")}</td>
                            <td className="px-2 py-1.5 text-muted-foreground">
                              {[s.enclosing_class, s.enclosing_function]
                                .filter(Boolean)
                                .join(".") || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {f.rules?.length ? (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground">Rule annotations</div>
                    {f.rules.map((r, i) => (
                      <div key={i} className="rounded border border-border/40 px-2 py-1.5 text-xs">
                        <span className="font-mono">{r.symbol}</span> · {r.kind} · {r.description}
                      </div>
                    ))}
                  </div>
                ) : null}
                {fileSuggestions.map((s, i) => (
                  <FindingCard key={i} change={s} refs={sim.official_references} />
                ))}
                {!fileSuggestions.length && f.suggested_changes?.length ? (
                  <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                    {f.suggested_changes.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function PlanTab({ sim }: { sim: UpgradeSimulation }) {
  const plan = sim.migration_plan || [];
  if (!plan.length) {
    return <p className="text-sm text-muted-foreground">No migration plan generated.</p>;
  }
  return (
    <div className="space-y-3 animate-fade-up">
      {plan.map((p) => (
        <div key={p.phase} className="rounded-md border border-border/70 p-4">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Badge className="border-primary/30 bg-primary/10 text-primary">Phase {p.phase}</Badge>
            <span className="font-medium">{p.title}</span>
            <Badge className="border-border text-muted-foreground">{p.difficulty}</Badge>
            <span className="text-xs text-muted-foreground">~{p.estimated_duration_hours}h</span>
          </div>
          <p className="text-sm text-muted-foreground">{p.description}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Why: </span>
            {p.reasoning}
          </p>
          {p.tasks?.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
              {p.tasks.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function SuggestionsTab({ sim }: { sim: UpgradeSimulation }) {
  const changes = sim.suggested_changes || [];
  const rules = sim.migration_rules || [];
  const intel = intelligenceOf(sim);
  if (!changes.length) {
    if (intel && !isStaleIntelligenceSimulation(sim)) {
      return (
        <p className="animate-fade-up text-sm text-muted-foreground">
          No per-file patches were generated. Category-level findings are in the Analysis tab.
        </p>
      );
    }
    const noKnowledge = rules.length === 0;
    return (
      <div className="space-y-3 animate-fade-up text-sm text-muted-foreground">
        <StatusCard
          status={noKnowledge ? "unknown" : "no_migration_required"}
          title={noKnowledge ? "Unknown" : "No changes required"}
          detail={
            noKnowledge
              ? "Insufficient deterministic migration knowledge for this library/version range. Do not treat this as a clean upgrade."
              : "Positively verified: deterministic rules exist and no call sites require a code change."
          }
          refs={sim.official_references || []}
        />
      </div>
    );
  }

  const auto = changes.filter((c) => resolveStatus(c) === "automatic_migration");
  const manual = changes.filter((c) => resolveStatus(c) === "manual_review_required");
  const unresolved = changes.filter((c) => resolveStatus(c) === "unresolved");
  const unknown = changes.filter((c) => resolveStatus(c) === "unknown");
  const none = changes.filter((c) => resolveStatus(c) === "no_migration_required");

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex flex-wrap gap-2 text-xs">
        <Badge className="border-success/40 bg-success/10 text-success">
          Automatic {auto.length}
        </Badge>
        <Badge className="border-warning/40 bg-warning/10 text-warning">
          Manual review {manual.length}
        </Badge>
        <Badge className="border-border text-muted-foreground">
          Unresolved {unresolved.length}
        </Badge>
        <Badge className="border-chart-2/40 bg-chart-2/10 text-chart-2">
          Unknown {unknown.length}
        </Badge>
        <Badge className="border-border text-muted-foreground">No changes {none.length}</Badge>
      </div>

      {auto.length ? (
        <section className="space-y-3">
          <h4 className="text-sm font-medium">Automatic migration available</h4>
          {auto.map((c, i) => (
            <FindingCard key={`auto-${i}`} change={c} showPath refs={sim.official_references} />
          ))}
        </section>
      ) : null}

      {manual.length ? (
        <section className="space-y-3">
          <h4 className="text-sm font-medium">Manual review required</h4>
          {manual.map((c, i) => (
            <FindingCard key={`man-${i}`} change={c} showPath refs={sim.official_references} />
          ))}
        </section>
      ) : null}

      {unresolved.length ? (
        <section className="space-y-3">
          <h4 className="text-sm font-medium">Unresolved</h4>
          {unresolved.map((c, i) => (
            <FindingCard key={`unr-${i}`} change={c} showPath refs={sim.official_references} />
          ))}
        </section>
      ) : null}

      {unknown.length ? (
        <section className="space-y-3">
          <h4 className="text-sm font-medium">Unknown</h4>
          {unknown.map((c, i) => (
            <FindingCard key={`unk-${i}`} change={c} showPath refs={sim.official_references} />
          ))}
        </section>
      ) : null}

      {none.length ? (
        <section className="space-y-3">
          <h4 className="text-sm font-medium">No changes required</h4>
          {none.map((c, i) => (
            <FindingCard key={`ok-${i}`} change={c} showPath refs={sim.official_references} />
          ))}
        </section>
      ) : null}
    </div>
  );
}

function RulesTab({ sim }: { sim: UpgradeSimulation }) {
  const rules = sim.migration_rules ?? [];
  if (!rules.length) {
    return (
      <p className="animate-fade-up text-sm text-muted-foreground">
        No structured migration rules matched for this upgrade range. See Affected Files and Official
        References for repository usage and docs.
      </p>
    );
  }
  return (
    <div className="space-y-2 animate-fade-up">
      {rules.map((r, i) => (
        <div key={r.id || i} className="rounded-md border border-border/70 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm">{r.symbol}</span>
            <Badge className="border-border text-muted-foreground">{r.kind}</Badge>
            <span className={`text-xs uppercase ${severityColor(r.severity)}`}>{r.severity}</span>
            {r.auto_fixable ? (
              <Badge className="border-success/40 bg-success/10 text-success">auto-fixable</Badge>
            ) : (
              <Badge className="border-border text-muted-foreground">manual</Badge>
            )}
            {r.unchanged ? (
              <Badge className="border-success/40 bg-success/10 text-success">compatible</Badge>
            ) : null}
            <span className="text-xs text-muted-foreground">
              {Math.round(r.confidence * 100)}% · {r.estimated_effort}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{r.description || r.reason}</p>
          {(r.before || r.after) && (
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              {r.before ? (
                <pre className="overflow-x-auto rounded bg-secondary/60 p-2 font-mono text-xs">
                  {r.before}
                </pre>
              ) : null}
              {r.after ? (
                <pre className="overflow-x-auto rounded border border-primary/20 bg-primary/5 p-2 font-mono text-xs">
                  {r.after}
                </pre>
              ) : null}
            </div>
          )}
          {r.official_reference ? <OfficialLink href={r.official_reference} /> : null}
        </div>
      ))}
    </div>
  );
}

function ReferencesTab({ sim }: { sim: UpgradeSimulation }) {
  const refs = migrationReferences(sim);

  if (!refs.length) {
    return (
      <div className="space-y-2 animate-fade-up text-sm text-muted-foreground">
        <p>Official migration documentation was not found.</p>
        <p>
          Repository analysis completed successfully. Manual review may be required. You can still
          check{" "}
          <a
            className="text-primary hover:underline"
            href={`https://pypi.org/project/${encodeURIComponent(sim.package_name)}/`}
            target="_blank"
            rel="noreferrer"
          >
            pypi.org/project/{sim.package_name}
          </a>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2 animate-fade-up">
      {refs.map((href) => (
        <a
          key={href}
          href={href}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-md border border-border/70 px-3 py-2 text-sm text-primary hover:bg-accent/40"
        >
          <BookOpen className="h-4 w-4 shrink-0" />
          <span className="min-w-0 flex-1 truncate font-mono text-xs">{href}</span>
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
        </a>
      ))}
    </div>
  );
}

function resolveStatus(
  change: NonNullable<UpgradeSimulation["suggested_changes"]>[number],
): SuggestedChangeStatus {
  return resolveSuggestedChangeStatus(change);
}

function FindingCard({
  change,
  showPath,
  refs,
}: {
  change: NonNullable<UpgradeSimulation["suggested_changes"]>[number];
  showPath?: boolean;
  refs?: string[] | null;
}) {
  const status = resolveStatus(change);
  const docLinks = [
    ...new Set(
      [change.official_reference, ...(refs || [])].filter(Boolean) as string[],
    ),
  ].slice(0, 5);

  if (status === "automatic_migration") {
    return <AutoPatchCard change={change} showPath={showPath} />;
  }

  const defaultTitle =
    change.status_title ||
    (status === "manual_review_required"
      ? "Manual review required"
      : status === "unknown"
        ? "Unknown"
        : status === "unresolved"
          ? "Unresolved"
          : "No changes required");

  return (
    <StatusCard
      status={status}
      title={defaultTitle}
      detail={change.status_detail || change.explanation}
      filePath={showPath ? change.file_path : undefined}
      line={change.line}
      symbol={change.symbol}
      currentCode={
        status === "manual_review_required" || status === "unknown" || status === "unresolved"
          ? change.current_code
          : undefined
      }
      confidence={change.confidence}
      analysisSource={change.analysis_source}
      refs={docLinks}
      aiGuidance={
        change.ai_explanation || change.ai_suggested_code
          ? {
              explanation: change.ai_explanation || change.reasoning || null,
              suggestedCode: change.ai_suggested_code || null,
            }
          : null
      }
    />
  );
}

function StatusCard({
  status,
  title,
  detail,
  filePath,
  line,
  symbol,
  currentCode,
  confidence,
  refs,
  aiGuidance,
  analysisSource,
}: {
  status: SuggestedChangeStatus;
  title: string;
  detail: string;
  filePath?: string;
  line?: number | null;
  symbol?: string | null;
  currentCode?: string;
  confidence?: number;
  refs?: string[];
  aiGuidance?: { explanation: string | null; suggestedCode: string | null } | null;
  analysisSource?: string | null;
}) {
  const tone =
    status === "no_migration_required"
      ? "border-success/30 bg-success/5"
      : status === "manual_review_required"
        ? "border-warning/40 bg-warning/5"
        : status === "unknown"
          ? "border-chart-2/40 bg-chart-2/5"
          : status === "unresolved"
            ? "border-border/70 bg-background/40"
            : "border-primary/30 bg-primary/5";
  const badge =
    status === "no_migration_required"
      ? "border-success/40 bg-success/10 text-success"
      : status === "manual_review_required"
        ? "border-warning/40 bg-warning/10 text-warning"
        : status === "unknown"
          ? "border-chart-2/40 bg-chart-2/10 text-chart-2"
          : status === "unresolved"
            ? "border-border text-muted-foreground"
            : "border-primary/40 bg-primary/10 text-primary";
  const sourceLabel = analysisSourceLabel(analysisSource);

  return (
    <div className={cn("rounded-md border p-3", tone)}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge className={badge}>{title}</Badge>
        {sourceLabel ? (
          <Badge className="border-border text-muted-foreground">{sourceLabel}</Badge>
        ) : null}
        {confidence != null ? (
          <span className="text-xs text-muted-foreground">
            {Math.round(confidence * 100)}% conf
          </span>
        ) : null}
      </div>
      {(filePath || symbol) && (
        <div className="mb-2 font-mono text-xs text-muted-foreground">
          {filePath || ""}
          {line != null ? `:${line}` : ""}
          {symbol ? ` · ${symbol}` : ""}
        </div>
      )}
      <p className="text-sm text-muted-foreground">{detail}</p>
      {currentCode && (status === "manual_review_required" || status === "unknown" || status === "unresolved") ? (
        <div className="mt-3">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Current usage
          </div>
          <pre className="mt-1 overflow-x-auto rounded bg-secondary/60 p-2 font-mono text-xs">
            {currentCode}
          </pre>
        </div>
      ) : null}
      {aiGuidance?.explanation || aiGuidance?.suggestedCode ? (
        <div className="mt-3 rounded border border-primary/20 bg-primary/5 p-2">
          <div className="text-[11px] uppercase tracking-wide text-primary">AI guidance</div>
          {aiGuidance.explanation ? (
            <p className="mt-1 text-xs text-muted-foreground">{aiGuidance.explanation}</p>
          ) : null}
          {aiGuidance.suggestedCode ? (
            <pre className="mt-2 overflow-x-auto rounded bg-secondary/60 p-2 font-mono text-xs">
              {aiGuidance.suggestedCode}
            </pre>
          ) : null}
        </div>
      ) : null}
      {status === "manual_review_required" || status === "unknown" || status === "unresolved" ? (
        <div className="mt-3 space-y-1">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Official documentation
          </div>
          {refs?.length ? (
            refs.map((href) => <OfficialLink key={href} href={href} />)
          ) : (
            <p className="text-xs text-muted-foreground">
              No documentation URL attached — check the Official References tab.
            </p>
          )}
        </div>
      ) : null}
      {status === "no_migration_required" && refs?.length ? (
        <div className="mt-2">
          <OfficialLink href={refs[0]} />
        </div>
      ) : null}
    </div>
  );
}

function AutoPatchCard({
  change,
  showPath,
}: {
  change: NonNullable<UpgradeSimulation["suggested_changes"]>[number];
  showPath?: boolean;
}) {
  const [showDiff, setShowDiff] = useState(false);
  const suggested = change.suggested_code || "";

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
      {showPath ? (
        <div className="mb-2 flex flex-wrap items-center gap-2 font-mono text-xs text-muted-foreground">
          <span>
            {change.file_path}
            {change.line != null ? `:${change.line}` : ""}
            {change.symbol ? ` · ${change.symbol}` : ""}
          </span>
          <Badge className="border-success/40 bg-success/10 text-success">
            Automatic migration available
          </Badge>
          <span>{Math.round(change.confidence * 100)}%</span>
        </div>
      ) : (
        <Badge className="mb-2 border-success/40 bg-success/10 text-success">
          Automatic migration available
        </Badge>
      )}
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Current</div>
      <pre className="mt-1 overflow-x-auto rounded bg-secondary/60 p-2 font-mono text-xs text-foreground">
        {change.current_code}
      </pre>
      <div className="my-2 flex justify-center text-muted-foreground">
        <ArrowDown className="h-4 w-4" />
      </div>
      <div className="text-[11px] uppercase tracking-wide text-primary">Suggested</div>
      <pre className="mt-1 overflow-x-auto rounded border border-primary/20 bg-card p-2 font-mono text-xs text-foreground">
        {suggested}
      </pre>
      {change.unified_diff ? (
        <div className="mt-2">
          <button
            className="text-xs text-primary hover:underline"
            onClick={() => setShowDiff((v) => !v)}
          >
            {showDiff ? "Hide unified diff" : "Show unified diff"}
          </button>
          {showDiff ? (
            <pre className="mt-1 overflow-x-auto rounded border border-border/60 bg-secondary/40 p-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {change.unified_diff}
            </pre>
          ) : null}
        </div>
      ) : null}
      <p className="mt-2 text-sm text-muted-foreground">{change.explanation}</p>
      {change.official_reference ? <OfficialLink href={change.official_reference} /> : null}
    </div>
  );
}

function OfficialLink({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
    >
      Official source <ExternalLink className="h-3 w-3" />
    </a>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md border border-border/50 p-3">
      <h4 className="mb-2 text-sm font-medium">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">None</p>
      ) : (
        <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
