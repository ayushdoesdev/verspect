"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
import {
  ENRICHMENT_ROTATION,
  enrichmentCountLabel,
  enrichmentPhaseCopy,
  type EnrichmentProgress,
} from "@/lib/jobs/enrichment";
import { cn } from "@/lib/utils";

/**
 * Detail card for the enrichment loop.
 * Does not repeat the stage title — only package, count, and deterministic phase.
 */
export function LiveEnrichmentStatus({
  enrichment,
  className,
  compact = false,
}: {
  enrichment: EnrichmentProgress | null | undefined;
  className?: string;
  compact?: boolean;
}) {
  const reduceMotion = useReducedMotion();
  const [tick, setTick] = useState(0);
  const complete = (enrichment?.phase || "").toLowerCase() === "complete";
  const phaseCopy = enrichmentPhaseCopy(enrichment?.phase);
  const packageName = enrichment?.package || null;
  const countLabel = enrichmentCountLabel(enrichment);

  useEffect(() => {
    if (complete || reduceMotion || phaseCopy) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 2800);
    return () => window.clearInterval(id);
  }, [complete, reduceMotion, phaseCopy, packageName]);

  const subStatus = complete
    ? "Dependency Intelligence Complete"
    : phaseCopy || ENRICHMENT_ROTATION[tick % ENRICHMENT_ROTATION.length];

  if (complete) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10",
          compact ? "px-3 py-2.5" : "px-3.5 py-3",
          className,
        )}
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
          <Check className="h-3 w-3" strokeWidth={3} />
        </span>
        <p className="text-xs font-medium text-emerald-400">
          Dependency Intelligence Complete
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border/60 bg-secondary/30",
        compact ? "px-3 py-2.5" : "px-3.5 py-3",
        className,
      )}
    >
      {!reduceMotion ? (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-1/2 opacity-[0.06]"
          style={{
            background:
              "linear-gradient(90deg, transparent, hsl(var(--primary)), transparent)",
          }}
          animate={{ x: ["-40%", "180%"] }}
          transition={{ repeat: Infinity, duration: 2.6, ease: "easeInOut" }}
        />
      ) : null}

      <div className="relative space-y-2.5">
        {packageName ? (
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                Current package
              </p>
              <AnimatePresence mode="wait">
                <motion.p
                  key={packageName}
                  initial={reduceMotion ? false : { opacity: 0, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduceMotion ? undefined : { opacity: 0, y: -3 }}
                  transition={{ duration: 0.18 }}
                  className="truncate font-mono text-sm font-medium text-foreground"
                >
                  {packageName}
                </motion.p>
              </AnimatePresence>
            </div>
            {countLabel ? (
              <p className="shrink-0 pt-0.5 text-[11px] tabular-nums text-muted-foreground">
                {countLabel}
              </p>
            ) : null}
          </div>
        ) : countLabel ? (
          <p className="text-[11px] tabular-nums text-muted-foreground">{countLabel}</p>
        ) : null}

        <div className="flex items-center gap-2 min-w-0">
          <span
            className={cn(
              "relative flex h-1.5 w-1.5 shrink-0",
              !reduceMotion &&
                "after:absolute after:inset-0 after:rounded-full after:bg-primary/35 after:animate-ping",
            )}
          >
            <span className="relative h-1.5 w-1.5 rounded-full bg-primary" />
          </span>
          <AnimatePresence mode="wait">
            <motion.p
              key={subStatus}
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={reduceMotion ? undefined : { opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="truncate text-xs text-muted-foreground"
            >
              {subStatus}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
