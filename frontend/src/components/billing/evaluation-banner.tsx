"use client";

import Link from "next/link";
import { useState } from "react";
import { Clock, Sparkles } from "lucide-react";
import { useEntitlements } from "@/lib/entitlements";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PremiumUpgradeModal } from "@/components/billing/premium-gate";

function daysLeft(trialEndsAt?: string | null): number | null {
  if (!trialEndsAt) return null;
  const end = Date.parse(trialEndsAt);
  if (!Number.isFinite(end)) return null;
  const ms = end - Date.now();
  if (ms <= 0) return 0;
  return Math.max(1, Math.ceil(ms / (24 * 60 * 60 * 1000)));
}

/** Persistent banner for active evaluation countdown or expired read-only mode. */
export function EvaluationBanner() {
  const entitlements = useEntitlements();
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  if (entitlements.loading || entitlements.plan !== "free") {
    return null;
  }

  if (entitlements.evaluationExpired || entitlements.readOnly) {
    return (
      <>
        <PremiumUpgradeModal
          open={upgradeOpen}
          onClose={() => setUpgradeOpen(false)}
          variant="evaluation"
        />
        <div className="mb-6 overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/15 via-card to-primary/10 px-4 py-3 sm:px-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-semibold tracking-tight">
                <Sparkles className="h-4 w-4 text-amber-400" />
                Your 7-day evaluation has ended
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground sm:text-sm">
                You can still sign in and browse repositories, scans, and reports. New imports,
                scans, sync, Upgrade Simulator, and background jobs require a paid plan. No data
                was deleted.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setUpgradeOpen(true)}
                className={cn(buttonVariants({ size: "sm" }))}
              >
                Upgrade to Starter
              </button>
              <Link
                href="/pricing"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                Compare plans
              </Link>
            </div>
          </div>
        </div>
      </>
    );
  }

  if (entitlements.evaluationActive) {
    const left = daysLeft(entitlements.trialEndsAt);
    return (
      <div className="mb-4 flex flex-col gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground sm:text-sm">
          <Clock className="h-3.5 w-3.5 text-primary" />
          <span>
            <span className="font-medium text-foreground">Evaluation Plan</span>
            {left != null ? (
              <>
                {" "}
                · {left} day{left === 1 ? "" : "s"} remaining to evaluate Verspect
              </>
            ) : (
              <> · intended for evaluating Verspect before a paid plan</>
            )}
          </span>
        </div>
        <Link
          href="/billing?plan=starter"
          className="text-xs font-medium text-primary hover:underline"
        >
          Upgrade anytime
        </Link>
      </div>
    );
  }

  return null;
}
