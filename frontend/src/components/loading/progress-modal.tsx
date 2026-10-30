"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, GitBranch, RefreshCw, X } from "lucide-react";
import { useJobs } from "@/lib/jobs/jobs-context";
import {
  AI_ADVISOR_ALIASES,
  AI_ADVISOR_STAGES,
  SCAN_ALIASES,
  scanTimeline,
  simulationTimeline,
  stageCopy,
  SCAN_STAGES,
  SYNC_STAGES,
  SIMULATION_STAGES,
} from "@/lib/jobs/stages";
import {
  enrichmentPhaseCopy,
  isEnrichmentStage,
} from "@/lib/jobs/enrichment";
import { jobStatusLabel } from "@/lib/jobs/status";
import { useEntitlements } from "@/lib/entitlements";
import { Button } from "@/components/ui/button";
import {
  ActivityTimeline,
  ProgressBar,
  estimateRemaining,
  formatElapsed,
} from "./activity-timeline";
import { LiveEnrichmentStatus } from "./live-enrichment-status";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function ProgressModal() {
  const {
    modalJob,
    setModalJob,
    dismissJob,
    cancelJobScan,
    retryJobScan,
    cancelJobSimulation,
    retryJobSimulation,
    workerStatus,
  } = useJobs();
  const entitlements = useEntitlements();
  const [now, setNow] = useState(Date.now());

  const waiting =
    !!modalJob && (modalJob.status === "pending" || modalJob.backendStartedAt == null);
  const terminal = !!modalJob && TERMINAL_STATUSES.has(modalJob.status);

  useEffect(() => {
    if (!modalJob || waiting || terminal) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [modalJob, waiting, terminal]);

  const isSimulation = modalJob?.kind === "simulation";
  const isAiAdvisor = modalJob?.kind === "ai_advisor";
  const isImport = modalJob?.kind === "import";

  // Cancel/retry route to the right pipeline — scans and simulations are
  // separate resources that share this modal.
  const cancel = useCallback(() => {
    if (!modalJob) return;
    if (isSimulation) {
      if (modalJob.dependencyId) {
        void cancelJobSimulation(modalJob.dependencyId, modalJob.resourceId);
      }
      return;
    }
    void cancelJobScan(modalJob.resourceId);
  }, [cancelJobScan, cancelJobSimulation, isSimulation, modalJob]);

  const retry = useCallback(() => {
    if (!modalJob) return;
    if (isSimulation) {
      if (modalJob.dependencyId) {
        void retryJobSimulation(modalJob.dependencyId, modalJob.resourceId);
      }
      return;
    }
    void retryJobScan(modalJob.resourceId);
  }, [isSimulation, modalJob, retryJobScan, retryJobSimulation]);

  // A simulation can only be controlled when we know its parent dependency.
  const canControl = !isSimulation || !!modalJob?.dependencyId;
  const open = !!modalJob;

  const scanKind =
    modalJob?.kind === "ai_advisor"
      ? "ai_advisor"
      : modalJob?.kind === "sync"
        ? "sync"
        : "scan";

  const rawSteps = modalJob
    ? isSimulation
      ? simulationTimeline(
          modalJob.currentStage,
          modalJob.progress,
          modalJob.status === "pending" ? "queued" : modalJob.status,
          {
            lockAiMigrationAssistant:
              !entitlements.loading && !entitlements.canGenerateAiMigration,
          },
        )
      : scanTimeline(
          modalJob.currentStage,
          modalJob.progress,
          modalJob.status === "completed"
            ? "completed"
            : modalJob.status === "failed"
              ? "failed"
              : modalJob.status === "cancelled"
                ? "cancelled"
                : modalJob.status === "pending"
                  ? "queued"
                  : "running",
          scanKind,
        )
    : [];

  const showEnrichment =
    !!modalJob &&
    !isSimulation &&
    !isAiAdvisor &&
    !waiting &&
    !terminal &&
    (isEnrichmentStage(modalJob.currentStage) ||
      modalJob.enrichment?.phase === "complete");

  const steps = rawSteps.map((step) => {
    if (step.key === "knowledge" && step.state === "completed") {
      return { ...step, copy: "Dependency Intelligence Complete" };
    }
    if (
      step.state === "running" &&
      isEnrichmentStage(step.key) &&
      modalJob?.enrichment
    ) {
      const phaseCopy = enrichmentPhaseCopy(modalJob.enrichment.phase);
      const pkg = modalJob.enrichment.package;
      const idx = modalJob.enrichment.index;
      const total = modalJob.enrichment.total;
      if (phaseCopy && pkg && typeof idx === "number" && typeof total === "number") {
        return { ...step, copy: `${phaseCopy} · ${pkg} (${idx} of ${total})` };
      }
      if (phaseCopy) return { ...step, copy: phaseCopy };
      if (pkg && typeof idx === "number" && typeof total === "number") {
        return { ...step, copy: `${pkg} (${idx} of ${total})` };
      }
    }
    return step;
  });

  const statusLabel = modalJob ? jobStatusLabel(modalJob) : "";

  const copy = modalJob?.workerOffline
    ? "Worker offline — background service unavailable"
    : modalJob?.stalled
      ? isImport
        ? "Repository import is taking longer than expected…"
        : "Still waiting for an available worker…"
      : waiting
        ? "Waiting in Queue…"
        : showEnrichment
          ? enrichmentPhaseCopy(modalJob.enrichment?.phase) ||
            (modalJob.enrichment?.package
              ? `Processing ${modalJob.enrichment.package}`
              : "Checking package versions…")
          : isSimulation
            ? stageCopy(SIMULATION_STAGES, modalJob?.currentStage, {})
            : isAiAdvisor
              ? stageCopy(AI_ADVISOR_STAGES, modalJob?.currentStage, AI_ADVISOR_ALIASES)
              : stageCopy(
                  modalJob?.kind === "sync" ? SYNC_STAGES : SCAN_STAGES,
                  modalJob?.currentStage,
                  SCAN_ALIASES,
                );

  const elapsed =
    modalJob && !waiting && modalJob.backendStartedAt != null
      ? now - modalJob.backendStartedAt
      : null;
  const eta =
    elapsed != null && modalJob && !terminal
      ? estimateRemaining(modalJob.progress, elapsed, modalJob.currentStage)
      : null;

  return (
    <AnimatePresence>
      {open && modalJob ? (
        <motion.div
          className="fixed inset-0 z-[80] flex items-end justify-center bg-black/55 p-4 backdrop-blur-sm sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setModalJob(null)}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={modalJob.title}
            className="w-full max-w-md overflow-hidden rounded-2xl border border-border/80 bg-card shadow-2xl"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-4">
              <div className="flex items-start gap-3">
                <motion.div
                  animate={
                    modalJob.status === "running"
                      ? { rotate: [0, -8, 8, 0] }
                      : { rotate: 0 }
                  }
                  transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
                  className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary"
                >
                  <GitBranch className="h-5 w-5" />
                </motion.div>
                <div>
                  <h2 className="text-base font-semibold tracking-tight">{modalJob.title}</h2>
                  {modalJob.subtitle ? (
                    <p className="mt-0.5 text-xs text-muted-foreground">{modalJob.subtitle}</p>
                  ) : null}
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Status: {statusLabel}
                    {modalJob.queuePosition && waiting && !modalJob.workerOffline
                      ? ` · Queue position ${modalJob.queuePosition}`
                      : ""}
                    {modalJob.retryCount ? ` · Retry ${modalJob.retryCount}` : ""}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Close"
                onClick={() => setModalJob(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="space-y-4 px-5 py-4">
              {modalJob.recovering ||
              (modalJob.currentStage || "").toLowerCase() === "recovering" ? (
                <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-sky-600 dark:text-sky-400">
                    <RefreshCw className="h-4 w-4 shrink-0 animate-spin" />
                    Recovering scan…
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    The previous worker stopped unexpectedly. Verspect reclaimed this scan and
                    is continuing automatically — you do not need to retry.
                  </p>
                </div>
              ) : modalJob.workerOffline ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-amber-500">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Worker Offline
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    Background processing service is unavailable. Your job stays queued and
                    resumes automatically once a worker reconnects.
                  </p>
                </div>
              ) : modalJob.stalled || (isImport && modalJob.status === "failed") ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-amber-500">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {isImport && modalJob.status === "failed"
                      ? "Import delayed"
                      : "Taking longer than expected"}
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {isImport
                      ? "Repository import is taking longer than expected. Retry safely cancels any stale worker ownership before starting a new scan. Cancel stops only this import — your repository record is kept."
                      : modalJob.queueBlocked
                        ? "The processing queue is congested, so this job has not started yet."
                        : "No worker has picked this job up yet. The worker may be busy or restarting."}{" "}
                    {!isImport ? "You can keep waiting, retry, or cancel." : null}
                  </p>
                  {isImport && canControl ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" onClick={retry}>
                        <RefreshCw className="mr-1 h-3 w-3" />
                        Retry Import
                      </Button>
                      {!terminal ? (
                        <Button size="sm" variant="outline" onClick={cancel}>
                          Cancel Import
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : modalJob.queueBlocked ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-muted-foreground">
                  Queue is congested
                  {workerStatus?.queued_total
                    ? ` — ${workerStatus.queued_total} job(s) waiting.`
                    : "."}
                </div>
              ) : null}

              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{copy}</span>
                  <span className="tabular-nums">{modalJob.progress}%</span>
                </div>
                <ProgressBar value={modalJob.progress} />
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                  {modalJob.workerOffline ? (
                    <span className="text-amber-500">Worker Offline</span>
                  ) : waiting ? (
                    <span>Waiting in Queue…</span>
                  ) : elapsed != null ? (
                    <span>Elapsed {formatElapsed(elapsed)}</span>
                  ) : null}
                  {eta ? <span>{eta}</span> : null}
                  {modalJob.workerName ? <span>Worker {modalJob.workerName}</span> : null}
                </div>
              </div>

              {showEnrichment ? (
                <LiveEnrichmentStatus enrichment={modalJob.enrichment} />
              ) : null}

              <div className="max-h-[42vh] overflow-y-auto pr-1">
                <ActivityTimeline steps={steps} />
              </div>

              {(modalJob.status === "failed" || modalJob.status === "cancelled") &&
              modalJob.error ? (
                <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {modalJob.error}
                </p>
              ) : null}
            </div>

            {/* Recovery actions are always present so a job can never trap the user. */}
            <div className="flex items-center justify-between gap-2 border-t border-border/60 px-5 py-3">
              <div className="flex items-center gap-2">
                {!terminal && canControl ? (
                  <Button size="sm" variant="destructive" onClick={cancel}>
                    {isImport ? "Cancel Import" : "Cancel"}
                  </Button>
                ) : null}
                {canControl ? (
                  <Button size="sm" variant="outline" onClick={retry}>
                    <RefreshCw className="mr-1 h-3 w-3" />
                    {isImport ? "Retry Import" : "Retry"}
                  </Button>
                ) : null}
              </div>
              <div className="flex gap-2">
                {terminal ? (
                  <Button size="sm" onClick={() => dismissJob(modalJob.id)}>
                    Close
                  </Button>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => setModalJob(null)}>
                    Run in background
                  </Button>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
