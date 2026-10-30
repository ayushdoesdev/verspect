"use client";

import { useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { GitBranch } from "lucide-react";
import {
  IMPORT_PRE_STAGES,
  type TimelineStep,
  type TimelineStepState,
} from "@/lib/jobs/stages";
import { ActivityTimeline } from "./activity-timeline";

type Phase = "idle" | "importing" | "handing_off";

/**
 * Client-side preflight timeline while the import API runs.
 * Scan progress takes over via JobsProvider after repositories are created.
 */
export function ImportProgressOverlay({
  open,
  phase,
  repoCount,
}: {
  open: boolean;
  phase: Phase;
  repoCount: number;
}) {
  const steps: TimelineStep[] = useMemo(() => {
    const states: TimelineStepState[] = ["completed", "completed", "pending"];
    if (phase === "importing") states[2] = "running";
    else if (phase === "handing_off") states[2] = "completed";
    return IMPORT_PRE_STAGES.map((s, i) => ({ ...s, state: states[i] }));
  }, [phase]);

  const progressLabel =
    phase === "handing_off"
      ? "Starting dependency analysis…"
      : "Importing metadata…";

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[85] flex items-end justify-center bg-black/55 p-4 backdrop-blur-sm sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="w-full max-w-md overflow-hidden rounded-2xl border border-border/80 bg-card shadow-2xl"
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12 }}
          >
            <div className="flex items-start gap-3 border-b border-border/60 px-5 py-4">
              <motion.div
                animate={{ rotate: [0, -10, 10, 0] }}
                transition={{ repeat: Infinity, duration: 2.2 }}
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary"
              >
                <GitBranch className="h-5 w-5" />
              </motion.div>
              <div>
                <h2 className="text-base font-semibold">Import Repository</h2>
                <p className="text-xs text-muted-foreground">
                  Connecting to GitHub and importing {repoCount} project
                  {repoCount === 1 ? "" : "s"}…
                </p>
              </div>
            </div>
            <div className="space-y-4 px-5 py-4">
              <div>
                <div className="mb-2 text-xs text-muted-foreground">{progressLabel}</div>
                <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
                  <motion.div
                    className="h-full w-1/3 rounded-full bg-primary"
                    animate={{ x: ["-20%", "220%"] }}
                    transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
                  />
                </div>
              </div>
              <ActivityTimeline steps={steps} />
              <p className="text-[11px] text-muted-foreground">
                Percent complete appears once the scan job reports backend progress.
              </p>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
