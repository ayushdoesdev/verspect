"use client";

import { motion } from "framer-motion";
import { Check, Circle, Loader2, Lock, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimelineStep } from "@/lib/jobs/stages";

export function ActivityTimeline({
  steps,
  className,
  compact = false,
}: {
  steps: TimelineStep[];
  className?: string;
  compact?: boolean;
}) {
  return (
    <ol className={cn("space-y-0", className)}>
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        return (
          <li key={`${step.key}-${i}`} className="relative flex gap-3">
            {!isLast ? (
              <span
                className={cn(
                  "absolute left-[11px] top-6 w-px",
                  compact ? "h-[calc(100%-8px)]" : "h-[calc(100%-4px)]",
                  step.state === "completed" ? "bg-emerald-500/60" : "bg-border",
                )}
                aria-hidden
              />
            ) : null}
            <div className="relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center">
              <StepIcon state={step.state} />
            </div>
            <div className={cn("min-w-0 flex-1 pb-4", isLast && "pb-0")}>
              <div
                className={cn(
                  "text-sm font-medium leading-6",
                  step.state === "completed" && "text-emerald-400",
                  step.state === "running" && "text-foreground",
                  step.state === "failed" && "text-destructive",
                  step.state === "pending" && "text-muted-foreground",
                  step.state === "locked" && "text-muted-foreground",
                )}
              >
                {step.state === "locked" ? `🔒 ${step.label}` : step.label}
              </div>
              {(step.state === "running" || step.state === "failed" || step.state === "locked") && (
                <motion.p
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "text-xs",
                    step.state === "failed" ? "text-destructive/80" : "text-muted-foreground",
                  )}
                >
                  {step.state === "failed" ? "Failed — retry available" : step.copy}
                </motion.p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function StepIcon({ state }: { state: TimelineStep["state"] }) {
  if (state === "completed") {
    return (
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400"
      >
        <Check className="h-3 w-3" strokeWidth={3} />
      </motion.span>
    );
  }
  if (state === "failed") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-destructive/20 text-destructive">
        <X className="h-3 w-3" strokeWidth={3} />
      </span>
    );
  }
  if (state === "locked") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Lock className="h-3 w-3" />
      </span>
    );
  }
  if (state === "running") {
    return (
      <motion.span
        animate={{ scale: [1, 1.12, 1] }}
        transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
        className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-primary"
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </motion.span>
    );
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center text-muted-foreground/70">
      <Circle className="h-3.5 w-3.5" />
    </span>
  );
}

export function ProgressBar({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, value || 0));
  return (
    <div className={cn("h-1.5 overflow-hidden rounded-full bg-secondary", className)}>
      <motion.div
        className="h-full rounded-full bg-primary"
        initial={false}
        animate={{ width: `${pct}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 24 }}
      />
    </div>
  );
}

export function formatElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return `${m}m ${rem}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

/** Stages where linear ETA extrapolation is misleading. */
const NO_ETA_STAGES = new Set([
  "ai",
  "analyzing_ai",
  "analyzing",
  "generating",
  "preparing",
  "ai_migration_assistant",
  "generating_suggestions",
  // Long deterministic enrichment — show package progress instead of ETAs.
  "knowledge",
  "versions",
  "vulnerabilities",
  "checking_versions",
  "checking_vulnerabilities",
  "checking_licenses",
]);

export function estimateRemaining(
  progress: number,
  elapsedMs: number,
  currentStage?: string | null,
): string | null {
  const stage = (currentStage || "").toLowerCase().replace(/\s+/g, "_");
  if (NO_ETA_STAGES.has(stage)) return null;
  if (progress <= 5 || progress >= 100 || elapsedMs < 2000) return null;
  // Late-stage work sits high on the bar — ETA would explode incorrectly.
  if (progress >= 90 && progress < 100) return null;
  const total = elapsedMs / (progress / 100);
  const rem = total - elapsedMs;
  if (rem < 1000) return null;
  return `~${formatElapsed(rem)} left`;
}
