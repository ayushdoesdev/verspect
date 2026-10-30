"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { useJobs } from "@/lib/jobs/jobs-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function ToastViewport() {
  const { toasts, dismissToast } = useJobs();

  return (
    <div className="pointer-events-none fixed top-4 right-4 z-[90] flex w-[min(100vw-2rem,22rem)] flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            className={cn(
              "pointer-events-auto flex gap-3 rounded-xl border px-3.5 py-3 shadow-lg backdrop-blur",
              t.tone === "success" && "border-emerald-500/30 bg-card/95",
              t.tone === "error" && "border-destructive/35 bg-card/95",
              t.tone === "info" && "border-border/70 bg-card/95",
            )}
          >
            <div className="mt-0.5">
              {t.tone === "success" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : t.tone === "error" ? (
                <AlertCircle className="h-4 w-4 text-destructive" />
              ) : (
                <Info className="h-4 w-4 text-primary" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{t.title}</div>
              {t.description ? (
                <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>
              ) : null}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              aria-label="Dismiss"
              onClick={() => dismissToast(t.id)}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
