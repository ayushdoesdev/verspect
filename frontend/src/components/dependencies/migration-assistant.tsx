"use client";

import { useMemo, useState, type ComponentType } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ArrowDown,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Expand,
  ExternalLink,
  FileCode2,
  Filter,
  Info,
  Search,
  ShieldAlert,
  Sparkles,
  Timer,
  GitPullRequest,
  Wrench,
} from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { cn, severityColor } from "@/lib/utils";
import {
  aggregateUsages,
  buildAssistantSummary,
  buildUnifiedPatch,
  classifyReference,
  confidenceBand,
  confidenceLabel,
  confidencePercent,
  estimateFixMinutes,
  filterAssistantItems,
  highConfidencePatches,
  migrationReferences,
  migrationStatusLabel,
  resolveFindingStatus,
  type MigrationOverallStatus,
} from "@/lib/migration-assistant";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { MigrationRule, SuggestedChange, UpgradeSimulation } from "@/types";

export function MigrationAssistant({ sim }: { sim: UpgradeSimulation }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [patchPreview, setPatchPreview] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [prBusy, setPrBusy] = useState(false);
  const [prError, setPrError] = useState<string | null>(null);
  const [prUrl, setPrUrl] = useState<string | null>(
    (sim.collected_sources as { github_pr_url?: string } | null)?.github_pr_url || null,
  );

  const summary = useMemo(() => buildAssistantSummary(sim), [sim]);
  const status = summary.status;
  const refs = useMemo(() => migrationReferences(sim), [sim]);
  const usages = useMemo(() => aggregateUsages(sim), [sim]);
  const patches = useMemo(() => highConfidencePatches(sim), [sim]);
  const filtered = useMemo(
    () => filterAssistantItems(sim, query, filter),
    [sim, query, filter],
  );

  async function copyText(key: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      /* ignore */
    }
  }

  function downloadPatch() {
    const body = buildUnifiedPatch(patches);
    const blob = new Blob([body], { type: "text/x-diff" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${sim.package_name}-${sim.from_version}-to-${sim.to_version}.patch`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function createPullRequest() {
    setPrError(null);
    const ok = window.confirm(
      "Create a GitHub pull request with validated patches? This will create a branch and open a PR. It will not merge automatically.",
    );
    if (!ok) return;
    setPrBusy(true);
    try {
      const result = await api.createMigrationPullRequest(sim.id, { confirm: true });
      setPrUrl(result.pull_request_url || null);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.detail || err.message : (err as Error).message;
      setPrError(message || "Unable to create pull request");
    } finally {
      setPrBusy(false);
    }
  }

  if (status === "in_progress") {
    return (
      <div className="rounded-xl border border-border/60 bg-card/40 p-6 text-sm text-muted-foreground animate-fade-up">
        Migration intelligence is still being generated. Official documentation will appear below
        as sources are collected.
      </div>
    );
  }

  const showGreatNews =
    status === "no_changes" &&
    summary.requireMigration === 0 &&
    (summary.unknownCount || 0) === 0 &&
    (summary.usageSites > 0 || (sim.affected_files || []).length > 0 || (sim.suggested_changes || []).length > 0);

  const showDocsMissing =
    status === "docs_unavailable" ||
    (refs.length === 0 &&
      summary.requireMigration === 0 &&
      summary.usageSites === 0 &&
      !(sim.migration_rules || []).length);

  const sources = (sim.collected_sources || {}) as Record<string, unknown>;
  const engineError =
    typeof sources.engine_error === "string" && sources.engine_error
      ? sources.engine_error
      : null;
  const aiError =
    typeof sources.ai_assistant_error === "string" && sources.ai_assistant_error
      ? sources.ai_assistant_error
      : null;
  const aiEnabled = sources.ai_migration_enabled === true;

  return (
    <div className="space-y-6 animate-fade-up">
      {engineError ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
          <div className="font-medium text-destructive">Migration engine error</div>
          <p className="mt-1 text-muted-foreground">{engineError}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Deterministic Upgrade Simulator retained repository usage analysis. Re-run the
            simulation after the issue is resolved.
          </p>
        </div>
      ) : null}
      {aiEnabled && aiError ? (
        <div className="rounded-xl border border-border/70 bg-card/50 px-4 py-3 text-sm">
          <div className="font-medium text-foreground">AI guidance unavailable</div>
          <p className="mt-1 text-muted-foreground">
            Deterministic simulation results are unchanged. You can retry AI guidance without
            altering the simulator verdict.
          </p>
        </div>
      ) : null}

      {/* Version timeline + status */}
      <section className="overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-primary/10 via-card/80 to-transparent p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
            ✦ Team Exclusive
          </span>
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <VersionPill label="Current" value={sim.from_version} />
            <ArrowDown className="h-4 w-4 rotate-[-90deg] text-muted-foreground" />
            <VersionPill label="Target" value={sim.to_version} accent />
          </div>
          <StatusBadge status={status} />
        </div>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          {sim.summary ||
            `Analyzed ${sim.package_name} usages in your repository against ${sim.from_version} → ${sim.to_version}.`}
        </p>
      </section>

      {/* Executive summary */}
      <section className="rounded-2xl border border-border/70 bg-card/50 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold tracking-tight">Repository migration summary</h3>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryStat label="Usage sites reviewed" value={String(summary.usageSites)} />
          <SummaryStat label="Migration required" value={String(summary.requireMigration)} />
          <SummaryStat label="Fully compatible" value={String(summary.fullyCompatible)} />
          <SummaryStat
            label="Estimated migration time"
            value={
              summary.estimatedMinutes >= 60
                ? `~${(summary.estimatedMinutes / 60).toFixed(1)}h`
                : `~${summary.estimatedMinutes} min`
            }
          />
          <SummaryStat label="Auto-fix opportunities" value={String(summary.autoFixes)} />
          <SummaryStat label="Manual migration work" value={String(summary.manualChanges)} />
          <SummaryStat
            label="Static analysis"
            value={`${confidencePercent(summary.confidence)}%`}
            hint={confidenceLabel(summary.confidence)}
          />
          <SummaryStat
            label="Affected files"
            value={String((sim.affected_files || []).length)}
          />
        </div>
      </section>

      {showGreatNews ? (
        <EmptyGreatNews />
      ) : null}

      {showDocsMissing && !showGreatNews ? (
        <EmptyDocsUnavailable />
      ) : null}

      {/* Search / filter */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search API, file, deprecated, breaking…"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(
            [
              ["all", "All"],
              ["automatic", "Auto-fix"],
              ["manual", "Manual"],
              ["compatible", "Compatible"],
              ["breaking", "Breaking"],
              ["deprecated", "Deprecated"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setFilter(id)}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs transition-colors",
                filter === id
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:bg-accent",
              )}
            >
              {id === "all" ? <Filter className="h-3 w-3" /> : null}
              {label}
            </button>
          ))}
        </div>
      </div>

      {!filtered.changes.length &&
      !filtered.rules.length &&
      !filtered.breaking.length &&
      !filtered.deprecated.length &&
      (query.trim() || filter !== "all") ? (
        <div className="rounded-xl border border-border/60 bg-card/40 px-4 py-6 text-center text-sm text-muted-foreground">
          No migration findings match your search or filter.
        </div>
      ) : null}

      {/* Auto-fix toolbar */}
      {patches.length > 0 ? (
        <section className="rounded-xl border border-success/30 bg-success/5 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-sm font-medium text-success">
                {patches.length} high-confidence patch{patches.length === 1 ? "" : "es"} ready
              </div>
              <p className="text-xs text-muted-foreground">
                Confidence ≥ 95% — safe to preview, copy, or download
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => setPatchPreview(true)}>
                <Wrench className="h-3.5 w-3.5" />
                Generate Patch
              </Button>
              <Button size="sm" variant="outline" onClick={() => setPatchPreview((v) => !v)}>
                {patchPreview ? "Hide preview" : "Preview Patch"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => copyText("patch", buildUnifiedPatch(patches))}
              >
                <Copy className="h-3.5 w-3.5" />
                {copied === "patch" ? "Copied" : "Copy Patch"}
              </Button>
              <Button size="sm" variant="outline" onClick={downloadPatch}>
                <Download className="h-3.5 w-3.5" />
                Download Patch
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={createPullRequest}
                disabled={prBusy}
              >
                <GitPullRequest className="h-3.5 w-3.5" />
                {prBusy ? "Creating PR…" : "Create GitHub PR"}
              </Button>
            </div>
          </div>
          {prUrl ? (
            <p className="mt-2 text-xs">
              <a href={prUrl} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                Open pull request
              </a>
            </p>
          ) : null}
          {prError ? <p className="mt-2 text-xs text-destructive">{prError}</p> : null}
          <AnimatePresence>
            {patchPreview ? (
              <motion.pre
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="max-h-64 overflow-auto rounded-lg bg-secondary/70 p-3 font-mono text-[11px] leading-relaxed"
              >
                {buildUnifiedPatch(patches)}
              </motion.pre>
            ) : null}
          </AnimatePresence>
        </section>
      ) : null}

      {/* Code change cards */}
      {filtered.changes.length ? (
        <section className="space-y-3">
          <SectionTitle icon={FileCode2} title="Code changes in your repository" />
          {filtered.changes.map((change, i) => (
            <ChangeCard
              key={`${change.file_path}-${change.line}-${i}`}
              change={change}
              expanded={!!expanded[`c-${i}`]}
              onToggle={() =>
                setExpanded((prev) => ({ ...prev, [`c-${i}`]: !prev[`c-${i}`] }))
              }
              onCopy={(text) => copyText(`c-${i}`, text)}
              copied={copied === `c-${i}`}
            />
          ))}
        </section>
      ) : null}

      {/* Rules as migration recipes */}
      {filtered.rules.length ? (
        <section className="space-y-3">
          <SectionTitle icon={Wrench} title="Migration recipes" />
          {filtered.rules.map((rule, i) => (
            <RuleCard
              key={rule.id || `${rule.symbol}-${i}`}
              rule={rule}
              usage={usages.find((u) => u.symbol === rule.symbol || rule.symbol.endsWith(u.symbol))}
              expanded={!!expanded[`r-${i}`]}
              onToggle={() =>
                setExpanded((prev) => ({ ...prev, [`r-${i}`]: !prev[`r-${i}`] }))
              }
              onCopy={(text) => copyText(`r-${i}`, text)}
              copied={copied === `r-${i}`}
            />
          ))}
        </section>
      ) : null}

      {/* Affected files + occurrence counts */}
      {(sim.affected_files || []).length ? (
        <section className="space-y-3">
          <SectionTitle icon={FileCode2} title="Affected files" />
          <div className="grid gap-2 md:grid-cols-2">
            {(sim.affected_files || []).map((f) => (
              <div
                key={f.file_path}
                className="rounded-xl border border-border/60 bg-card/40 px-3 py-2.5"
              >
                <div className="truncate font-mono text-sm">{f.file_path}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {(f.usage_sites?.length || f.affected_apis?.length || 1)} occurrence
                  {(f.usage_sites?.length || f.affected_apis?.length || 1) === 1 ? "" : "s"}
                  {f.affected_apis?.length
                    ? ` · ${f.affected_apis.slice(0, 3).join(", ")}`
                    : ""}
                </div>
              </div>
            ))}
          </div>
          {usages.length ? (
            <div className="mt-2 space-y-2">
              {usages.slice(0, 8).map((u) => (
                <div
                  key={u.symbol}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/50 px-3 py-2 text-sm"
                >
                  <span className="font-mono text-primary">{u.symbol}()</span>
                  <span className="text-xs text-muted-foreground">
                    Used {u.count} time{u.count === 1 ? "" : "s"} across {u.files.size} file
                    {u.files.size === 1 ? "" : "s"}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* Breaking changes */}
      {filtered.breaking.length ? (
        <section className="space-y-3">
          <SectionTitle icon={ShieldAlert} title="Breaking changes" />
          {filtered.breaking.map((b, i) => {
            const files = (sim.affected_files || [])
              .filter(
                (f) =>
                  f.affected_apis?.some((a) => a.includes(b.symbol)) ||
                  f.usage_sites?.some(
                    (s) =>
                      s.symbol === b.symbol ||
                      s.fully_qualified_name === b.fully_qualified_name,
                  ),
              )
              .map((f) => f.file_path);
            const mins = estimateFixMinutes(null, b.confidence);
            return (
              <div
                key={`${b.fully_qualified_name}-${i}`}
                className="rounded-xl border border-destructive/30 bg-destructive/5 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="font-medium">{b.symbol}</h4>
                  <span className={cn("text-xs uppercase", severityColor(b.severity || "medium"))}>
                    {b.severity || "unknown"}
                  </span>
                  <ConfidenceBadge confidence={b.confidence} />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{b.reason}</p>
                {b.replacement ? (
                  <p className="mt-1 text-xs text-primary">Replacement: {b.replacement}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>Files: {files.length ? files.join(", ") : "see Affected Files"}</span>
                  <span>Complexity: {b.confidence >= 0.9 ? "Low" : b.confidence >= 0.7 ? "Medium" : "High"}</span>
                  <span className="inline-flex items-center gap-1">
                    <Timer className="h-3 w-3" /> ~{mins} min
                  </span>
                </div>
              </div>
            );
          })}
        </section>
      ) : null}

      {/* Deprecated APIs */}
      {filtered.deprecated.length ? (
        <section className="space-y-3">
          <SectionTitle icon={AlertTriangle} title="Deprecated APIs" />
          {filtered.deprecated.map((d, i) => {
            const usage = usages.find(
              (u) =>
                u.symbol === d.symbol ||
                d.fully_qualified_name.endsWith(u.symbol) ||
                u.symbol.endsWith(d.symbol),
            );
            const auto = (sim.suggested_changes || []).some(
              (c) =>
                c.symbol === d.symbol &&
                resolveFindingStatus(c) === "automatic_migration" &&
                c.confidence >= 0.95,
            );
            return (
              <div
                key={`${d.fully_qualified_name}-${i}`}
                className="rounded-xl border border-warning/30 bg-warning/5 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm">{d.fully_qualified_name}</span>
                  <ConfidenceBadge confidence={d.confidence} />
                  {auto ? (
                    <Badge className="border-success/40 bg-success/10 text-success">
                      Auto-fix available
                    </Badge>
                  ) : (
                    <Badge className="border-border text-muted-foreground">Manual</Badge>
                  )}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{d.reason}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>Replacement: {d.replacement || "See official docs"}</span>
                  <span>Repo usage: {usage?.count ?? 0}</span>
                </div>
              </div>
            );
          })}
        </section>
      ) : null}

      {/* Official references */}
      <section className="space-y-3">
        <SectionTitle icon={ExternalLink} title="Official references" />
        {refs.length ? (
          <div className="space-y-2">
            {refs.map((href) => (
              <a
                key={href}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-3 rounded-xl border border-border/60 px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent/30"
              >
                <Badge className="shrink-0 border-border text-muted-foreground">
                  {classifyReference(href)}
                </Badge>
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-primary">
                  {href}
                </span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </a>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Official migration documentation was not found. Repository analysis completed
            successfully. Manual review may be required.
          </p>
        )}
      </section>
    </div>
  );
}

function VersionPill({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-3 py-2",
        accent ? "border-primary/40 bg-primary/10" : "border-border/70 bg-background/50",
      )}
    >
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-mono text-sm font-medium">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: MigrationOverallStatus }) {
  const styles: Record<MigrationOverallStatus, string> = {
    no_changes: "border-success/40 bg-success/10 text-success",
    unknown: "border-chart-2/40 bg-chart-2/10 text-chart-2",
    unresolved: "border-border text-muted-foreground",
    breaking: "border-destructive/40 bg-destructive/10 text-destructive",
    deprecated: "border-warning/40 bg-warning/10 text-warning",
    manual_review: "border-warning/40 bg-warning/10 text-warning",
    docs_unavailable: "border-border text-muted-foreground",
    in_progress: "border-primary/40 bg-primary/10 text-primary",
  };
  const Icon =
    status === "no_changes"
      ? CheckCircle2
      : status === "unknown" || status === "manual_review" || status === "unresolved"
        ? Info
        : status === "breaking" || status === "deprecated"
          ? AlertTriangle
          : Sparkles;
  return (
    <Badge className={cn("gap-1.5 px-3 py-1.5 text-xs", styles[status])}>
      <Icon className="h-3.5 w-3.5" />
      {migrationStatusLabel(status)}
    </Badge>
  );
}

function SummaryStat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border/50 bg-background/40 px-3 py-2.5">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums">{value}</div>
      {hint ? <div className="text-[10px] text-muted-foreground">{hint}</div> : null}
    </div>
  );
}

function SectionTitle({
  icon: Icon,
  title,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-primary" />
      <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const band = confidenceBand(confidence);
  const pct = confidencePercent(confidence);
  return (
    <Badge
      className={cn(
        "border",
        band === "high" && "border-success/40 bg-success/10 text-success",
        band === "medium" && "border-warning/40 bg-warning/10 text-warning",
        band === "low" && "border-destructive/30 bg-destructive/10 text-destructive",
      )}
    >
      {pct}% · {confidenceLabel(confidence)}
    </Badge>
  );
}

function EmptyGreatNews() {
  return (
    <div className="rounded-2xl border border-success/30 bg-success/5 p-6 text-center">
      <CheckCircle2 className="mx-auto mb-3 h-8 w-8 text-success" />
      <h3 className="text-base font-semibold">Great news!</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
        No code changes are required for this upgrade. All detected API usages are compatible with
        the target version.
      </p>
    </div>
  );
}

function EmptyDocsUnavailable() {
  return (
    <div className="rounded-2xl border border-border/70 bg-card/40 p-6">
      <div className="flex items-start gap-3">
        <Info className="mt-0.5 h-5 w-5 text-muted-foreground" />
        <div>
          <h3 className="text-sm font-semibold">Official migration documentation was not found.</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Repository analysis completed successfully. Manual review may be required.
          </p>
        </div>
      </div>
    </div>
  );
}

function ChangeCard({
  change,
  expanded,
  onToggle,
  onCopy,
  copied,
}: {
  change: SuggestedChange;
  expanded: boolean;
  onToggle: () => void;
  onCopy: (text: string) => void;
  copied: boolean;
}) {
  const [fullCode, setFullCode] = useState(false);
  const status = resolveFindingStatus(change);
  const needsChange =
    status === "automatic_migration" || status === "manual_review_required";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border",
        status === "no_migration_required" && "border-success/25 bg-success/5",
        status === "automatic_migration" && "border-primary/30 bg-primary/5",
        status === "manual_review_required" && "border-warning/30 bg-warning/5",
        status === "unknown" && "border-chart-2/30 bg-chart-2/5",
        status === "unresolved" && "border-border/70 bg-background/40",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {status === "no_migration_required" ? (
              <Badge className="border-success/40 bg-success/10 text-success">
                No changes required
              </Badge>
            ) : status === "automatic_migration" ? (
              <Badge className="border-primary/40 bg-primary/10 text-primary">
                Automatic migration available
              </Badge>
            ) : status === "unknown" ? (
              <Badge className="border-chart-2/40 bg-chart-2/10 text-chart-2">Unknown</Badge>
            ) : status === "unresolved" ? (
              <Badge className="border-border text-muted-foreground">
                {change.status_title || "Unresolved"}
              </Badge>
            ) : (
              <Badge className="border-warning/40 bg-warning/10 text-warning">
                Manual review required
              </Badge>
            )}
            <ConfidenceBadge confidence={change.confidence} />
          </div>
          <div className="mt-1.5 font-mono text-xs text-muted-foreground">
            {change.file_path}
            {change.line != null ? `:${change.line}` : ""}
            {change.symbol ? ` · ${change.symbol}` : ""}
          </div>
        </div>
        {expanded ? (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-border/50 px-4 py-3"
          >
            {status === "unresolved" ? (
              <div className="space-y-2 text-sm">
                <p className="text-foreground">{change.status_title || "Unresolved"}</p>
                <p className="text-muted-foreground">
                  {change.status_detail ||
                    change.explanation ||
                    "Unresolved — insufficient evidence after deterministic and AI analysis."}
                </p>
                {change.current_code ? (
                  <pre className="overflow-x-auto rounded-lg bg-secondary/60 p-3 font-mono text-xs">
                    {change.current_code}
                  </pre>
                ) : null}
              </div>
            ) : status === "unknown" ? (
              <div className="space-y-2 text-sm">
                <p className="text-chart-2">Unknown — insufficient deterministic knowledge.</p>
                <p className="text-muted-foreground">
                  {change.explanation ||
                    "Do not treat this upgrade as clean until migration rules are available."}
                </p>
                {change.ai_explanation || change.ai_suggested_code ? (
                  <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-primary">
                      AI guidance
                    </div>
                    {change.ai_explanation ? (
                      <p className="mt-1 text-muted-foreground">{change.ai_explanation}</p>
                    ) : null}
                    {change.ai_suggested_code ? (
                      <pre className="mt-2 overflow-x-auto rounded bg-secondary/60 p-2 font-mono text-xs">
                        {change.ai_suggested_code}
                      </pre>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : status === "no_migration_required" ? (
              <div className="space-y-2 text-sm">
                <p className="text-success">No changes required.</p>
                <p className="text-muted-foreground">
                  {change.explanation ||
                    "Positively verified: this API is compatible with the target version."}
                </p>
                {change.current_code ? (
                  <pre className="overflow-x-auto rounded-lg bg-secondary/60 p-3 font-mono text-xs">
                    {change.current_code}
                  </pre>
                ) : null}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <CodeBlock
                    title="Current code"
                    code={change.current_code || ""}
                    expanded={fullCode}
                  />
                  <CodeBlock
                    title="Updated code"
                    code={change.suggested_code || "# Manual review required"}
                    accent
                    expanded={fullCode}
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">Reason: </span>
                  {change.explanation}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      onCopy(
                        [
                          change.current_code || "",
                          "---",
                          change.suggested_code || "",
                        ].join("\n"),
                      )
                    }
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copied ? "Copied" : "Copy"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setFullCode((v) => !v)}
                  >
                    <Expand className="h-3.5 w-3.5" />
                    {fullCode ? "Collapse" : "Expand"}
                  </Button>
                  {change.unified_diff ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onCopy(change.unified_diff || "")}
                    >
                      Copy diff
                    </Button>
                  ) : null}
                  {needsChange && change.confidence >= 0.95 && change.suggested_code ? (
                    <Badge className="border-success/40 bg-success/10 text-success">
                      Included in Generate Patch
                    </Badge>
                  ) : null}
                </div>
              </div>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function RuleCard({
  rule,
  usage,
  expanded,
  onToggle,
  onCopy,
  copied,
}: {
  rule: MigrationRule;
  usage?: { count: number; files: Set<string> };
  expanded: boolean;
  onToggle: () => void;
  onCopy: (text: string) => void;
  copied: boolean;
}) {
  const noChange = !!rule.unchanged || (!rule.after && !rule.before);

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/40">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium">{rule.symbol}</span>
            <Badge className="border-border text-muted-foreground">{rule.kind}</Badge>
            <span className={cn("text-xs uppercase", severityColor(rule.severity))}>
              {rule.severity}
            </span>
            <ConfidenceBadge confidence={rule.confidence} />
            {rule.auto_fixable ? (
              <Badge className="border-success/40 bg-success/10 text-success">auto-fixable</Badge>
            ) : null}
          </div>
          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
            {rule.description || rule.reason}
          </p>
          {usage ? (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Used {usage.count} time{usage.count === 1 ? "" : "s"} across {usage.files.size} file
              {usage.files.size === 1 ? "" : "s"}
            </p>
          ) : null}
        </div>
        {expanded ? (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="mt-1 h-4 w-4 shrink-0" />
        )}
      </button>
      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-border/50 px-4 py-3"
          >
            {noChange && !rule.after ? (
              <div className="space-y-2 text-sm">
                <p className="text-success">No changes required.</p>
                <p className="text-muted-foreground">
                  {rule.reason ||
                    rule.description ||
                    "Positively verified: this API is compatible with the target version."}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <CodeBlock title="Current" code={rule.before || rule.symbol} />
                  <CodeBlock
                    title="New"
                    code={rule.after || "# See official documentation"}
                    accent
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">Reason: </span>
                  {rule.reason || rule.description}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      onCopy([rule.before || "", "→", rule.after || ""].join("\n"))
                    }
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copied ? "Copied" : "Copy"}
                  </Button>
                  {rule.official_reference ? (
                    <a
                      href={rule.official_reference}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      Official docs <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              </div>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function CodeBlock({
  title,
  code,
  accent,
  expanded,
}: {
  title: string;
  code: string;
  accent?: boolean;
  expanded?: boolean;
}) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>
      <pre
        className={cn(
          "overflow-auto rounded-xl p-3 font-mono text-xs leading-relaxed",
          expanded ? "max-h-[32rem]" : "max-h-56",
          accent
            ? "border border-primary/25 bg-primary/5"
            : "bg-secondary/70",
        )}
      >
        {code}
      </pre>
    </div>
  );
}
