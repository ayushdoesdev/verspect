"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Lock, Sparkles, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TEAM_BENEFITS = [
  "Exact code replacements",
  "Line-by-line migration guidance",
  "AI-generated patches",
  "Side-by-side code diff",
  "Patch preview & confidence scores",
  "Organizations, RBAC & audit logs",
  "Repository sharing & team dashboard",
  "Opt-in GitHub pull requests after review",
];

const STARTER_BENEFITS = [
  "10 repositories",
  "Dependency graph & version analysis",
  "Upgrade Simulator",
  "Background jobs",
  "Export reports",
  "Email support",
];

const PRO_BENEFITS = [
  "Everything in Starter",
  "Unlimited repositories & scans",
  "GitHub inbound webhooks",
  "Scheduled scans",
  "Priority processing",
  "Advanced reports",
  "AI Upgrade Advisor",
];

const EVALUATION_BENEFITS = [
  "Restore repository imports & scans",
  "Repository sync & background jobs",
  "Upgrade Simulator analysis",
  "Up to 10 repositories on Starter",
  "Export reports & email support",
  "Your existing data stays intact",
];

export function PremiumUpgradeModal({
  open,
  onClose,
  variant = "team",
}: {
  open: boolean;
  onClose: () => void;
  variant?: "evaluation" | "starter" | "pro" | "team";
}) {
  const isTeam = variant === "team";
  const isStarter = variant === "starter";
  const isEvaluation = variant === "evaluation";
  const benefits = isTeam
    ? TEAM_BENEFITS
    : isEvaluation
      ? EVALUATION_BENEFITS
      : isStarter
        ? STARTER_BENEFITS
        : PRO_BENEFITS;
  const href = isTeam
    ? "/billing?plan=team"
    : isEvaluation || isStarter
      ? "/billing?plan=starter"
      : "/billing?plan=pro";
  const title = isTeam
    ? "Unlock AI Migration Assistant"
    : isEvaluation
      ? "Your evaluation has ended"
      : isStarter
        ? "Upgrade to Starter"
        : "Unlock Pro features";
  const subtitle = isTeam
    ? "Available on Team and Enterprise — code generation that ships:"
    : isEvaluation
      ? "Upgrade to keep scanning, syncing, and simulating upgrades. Nothing was deleted:"
      : isStarter
        ? "Built for individual developers:"
        : "Available on Pro, Team, and Enterprise:";
  const cta = isTeam
    ? "Upgrade to Team"
    : isEvaluation || isStarter
      ? "Upgrade to Starter — $19/mo"
      : "Upgrade to Pro";
  const badge = isTeam
    ? "Team Exclusive"
    : isEvaluation
      ? "Evaluation Ended"
      : isStarter
        ? "Most Popular"
        : "Pro Feature";

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="upgrade-modal-title"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            className="relative z-10 w-full max-w-lg overflow-hidden rounded-2xl border border-primary/30 bg-card shadow-2xl"
          >
            <div className="bg-gradient-to-br from-primary/25 via-chart-2/10 to-transparent px-6 pb-4 pt-6">
              <button
                type="button"
                onClick={onClose}
                className="absolute right-3 top-3 rounded-md p-1.5 text-muted-foreground hover:bg-accent"
              >
                <X className="h-4 w-4" />
              </button>
              <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                {badge}
              </div>
              <h2 id="upgrade-modal-title" className="text-xl font-semibold tracking-tight">
                {title}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
            </div>
            <div className="space-y-4 px-6 py-5">
              <ul className="space-y-2.5">
                {benefits.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Link href={href} className={cn(buttonVariants(), "flex-1")}>
                  {cta}
                </Link>
                <Button variant="outline" className="flex-1" onClick={onClose}>
                  Not now
                </Button>
              </div>
              <p className="text-center text-[11px] text-muted-foreground">
                Upgrade Simulator analyzes on every plan. AI Migration Assistant generates code on
                Team+.
              </p>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function PremiumBadge({
  variant = "team",
}: {
  variant?: "starter" | "pro" | "team" | "locked";
}) {
  if (variant === "locked") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <Lock className="h-3 w-3" />
        Locked
      </span>
    );
  }
  if (variant === "pro") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-chart-2/40 bg-chart-2/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-chart-2">
        Pro
      </span>
    );
  }
  if (variant === "starter") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
        Starter
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
      <Sparkles className="h-3 w-3" />
      Team
    </span>
  );
}

export function MigrationAssistantLockedCard({
  onUpgrade,
}: {
  onUpgrade?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-border/70 bg-card/50 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <PremiumBadge variant="team" />
          </div>
          <h3 className="text-lg font-semibold tracking-tight">AI Migration Assistant</h3>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            AI Migration Assistant analyzes your actual repository code and tells you exactly which
            lines to change — with replacements, explanations, and patch-ready output. Available on
            Team and Enterprise only. Upgrade Simulator analysis remains available on your current
            plan.
          </p>
        </div>
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {TEAM_BENEFITS.slice(0, 6).map((item) => (
          <li key={item} className="flex items-start gap-2 text-sm text-muted-foreground">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            {item}
          </li>
        ))}
      </ul>
      <div className="mt-5">
        {onUpgrade ? (
          <Button onClick={onUpgrade}>Upgrade to Team</Button>
        ) : (
          <Link href="/billing?plan=team" className={cn(buttonVariants())}>
            Upgrade to Team
          </Link>
        )}
      </div>
    </div>
  );
}
