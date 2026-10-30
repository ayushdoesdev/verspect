"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  X,
  XCircle,
} from "lucide-react";
import { useJobs } from "@/lib/jobs/jobs-context";
import {
  AI_ADVISOR_ALIASES,
  AI_ADVISOR_STAGES,
  SCAN_ALIASES,
  SCAN_STAGES,
  SIMULATION_STAGES,
  SYNC_STAGES,
  stageCopy,
} from "@/lib/jobs/stages";
import {
  enrichmentPhaseCopy,
  isEnrichmentStage,
} from "@/lib/jobs/enrichment";
import { jobStatusLabel } from "@/lib/jobs/status";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ProgressBar, estimateRemaining, formatElapsed } from "./activity-timeline";
import { LiveEnrichmentStatus } from "./live-enrichment-status";

export function JobsPanel() {
  const { activeJobs, setModalJob, dismissJob, workerStatus } = useJobs();
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(Date.now());

  const hasWork = activeJobs.length > 0;

  useEffect(() => {
    if (!activeJobs.length) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [activeJobs.length]);

  useEffect(() => {
    if (activeJobs.length > 0) setOpen(true);
  }, [activeJobs.length]);

  if (!hasWork) return null;

  // Sit above the floating Feedback button (bottom-5 right-5) so it stays clickable.
  return (
    <div className="fixed bottom-20 right-4 z-[70] w-[min(100vw-2rem,22rem)]">
      <motion.div
        layout
        className="overflow-hidden rounded-xl border border-border/80 bg-card/95 shadow-xl backdrop-blur"
      >
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 px-3.5 py-2.5 text-left"
          onClick={() => setOpen((v) => !v)}
        >
          <div className="flex items-center gap-2">
            {workerStatus && !workerStatus.online ? (
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            )}
            <div>
              <div className="text-sm font-medium">
                {activeJobs.length} job{activeJobs.length === 1 ? "" : "s"} running
              </div>
              {workerStatus && !workerStatus.online ? (
                <div className="text-[11px] text-amber-500">
                  Worker Offline — background processing is unavailable
                </div>
              ) : activeJobs[0] ? (
                <div className="text-[11px] text-muted-foreground">
                  {activeJobs[0].title} · {activeJobs[0].progress}%
                </div>
              ) : null}
            </div>
          </div>
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        </button>

        <AnimatePresence initial={false}>
          {open ? (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-t border-border/60"
            >
              <ul className="max-h-72 space-y-2 overflow-y-auto p-2.5">
                {activeJobs.slice(0, 8).map((job) => {
                  const waiting = job.status === "pending" || job.backendStartedAt == null;
                  const elapsed =
                    !waiting && job.backendStartedAt != null
                      ? now - job.backendStartedAt
                      : null;
                  const eta =
                    elapsed != null
                      ? estimateRemaining(job.progress, elapsed, job.currentStage)
                      : null;
                  const enrichmentLive =
                    !waiting &&
                    job.kind !== "simulation" &&
                    job.kind !== "ai_advisor" &&
                    (isEnrichmentStage(job.currentStage) ||
                      job.enrichment?.phase === "complete");
                  const copy = job.workerOffline
                    ? "Background service unavailable"
                    : job.stalled
                      ? "No worker available yet"
                      : waiting
                      ? "Waiting in Queue…"
                      : enrichmentLive
                        ? enrichmentPhaseCopy(job.enrichment?.phase) ||
                          (job.enrichment?.package
                            ? `Processing ${job.enrichment.package}`
                            : "Checking package versions…")
                        : job.kind === "simulation"
                          ? stageCopy(SIMULATION_STAGES, job.currentStage)
                          : job.kind === "ai_advisor"
                            ? stageCopy(
                                AI_ADVISOR_STAGES,
                                job.currentStage,
                                AI_ADVISOR_ALIASES,
                              )
                            : stageCopy(
                                job.kind === "sync" ? SYNC_STAGES : SCAN_STAGES,
                                job.currentStage,
                                SCAN_ALIASES,
                              );
                  return (
                    <li
                      key={job.id}
                      className="rounded-lg border border-border/50 bg-background/40 p-2.5"
                    >
                      <div className="mb-1.5 flex items-start justify-between gap-2">
                        <button
                          type="button"
                          className="min-w-0 text-left"
                          onClick={() => setModalJob(job.id)}
                        >
                          <div className="truncate text-xs font-medium">{job.title}</div>
                          {job.subtitle ? (
                            <div className="truncate text-[11px] text-muted-foreground">
                              {job.subtitle}
                            </div>
                          ) : null}
                        </button>
                        <div className="flex items-center gap-1">
                          <StatusIcon
                            status={
                              job.workerOffline
                                ? "offline"
                                : job.stalled
                                  ? "stalled"
                                  : job.status
                            }
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            aria-label="Dismiss"
                            onClick={() => dismissJob(job.id)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      <ProgressBar value={waiting ? 0 : job.progress} className="mb-1.5" />
                      {enrichmentLive ? (
                        <LiveEnrichmentStatus
                          enrichment={job.enrichment}
                          compact
                          className="mb-1.5"
                        />
                      ) : null}
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
                        <span>{jobStatusLabel(job)}</span>
                        <span>·</span>
                        {!waiting ? (
                          <span className="tabular-nums">{job.progress}%</span>
                        ) : null}
                        {!waiting ? <span>·</span> : null}
                        <span className="truncate">{copy}</span>
                        {waiting && job.queuePosition && !job.workerOffline ? (
                          <>
                            <span>·</span>
                            <span>Queue #{job.queuePosition}</span>
                          </>
                        ) : null}
                        {elapsed != null ? (
                          <>
                            <span>·</span>
                            <span>{formatElapsed(elapsed)}</span>
                          </>
                        ) : null}
                        {eta ? (
                          <>
                            <span>·</span>
                            <span>{eta}</span>
                          </>
                        ) : null}
                        {job.workerName ? (
                          <>
                            <span>·</span>
                            <span className="truncate">Worker {job.workerName}</span>
                          </>
                        ) : null}
                        {job.retryCount ? (
                          <>
                            <span>·</span>
                            <span>Retry {job.retryCount}</span>
                          </>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") {
    return <CheckCircle2 className={cn("h-3.5 w-3.5 text-emerald-400")} />;
  }
  if (status === "failed") {
    return <XCircle className="h-3.5 w-3.5 text-destructive" />;
  }
  if (status === "cancelled") {
    return <Ban className="h-3.5 w-3.5 text-muted-foreground" />;
  }
  if (status === "offline" || status === "stalled") {
    return <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />;
  }
  if (status === "pending") {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />;
  }
  return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
}
