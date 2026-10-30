"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowDown,
  Check,
  FileCode2,
  Lock,
  Sparkles,
  Timer,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PremiumBadge, PremiumUpgradeModal } from "@/components/billing/premium-gate";
import { useState, type ComponentType } from "react";

/** Flagship locked landing — shown to Free, Starter & Pro users. */
export function MigrationAssistantLanding({
  onUpgrade,
}: {
  onUpgrade?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const openUpgrade = () => {
    setOpen(true);
    onUpgrade?.();
  };

  return (
    <div className="space-y-10">
      <PremiumUpgradeModal open={open} onClose={() => setOpen(false)} />

      <motion.section
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl border border-primary/25 bg-gradient-to-br from-primary/20 via-card to-chart-2/10 px-6 py-10 sm:px-10"
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-primary/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 left-10 h-48 w-48 rounded-full bg-chart-2/15 blur-3xl" />
        <div className="relative max-w-3xl">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <PremiumBadge variant="team" />
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Lock className="h-3.5 w-3.5" />
              Team & Enterprise Exclusive
            </span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl md:text-5xl">
            AI Migration Assistant
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            See exactly what code must change before upgrading a dependency.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button size="lg" onClick={openUpgrade}>
              <Sparkles className="h-4 w-4" />
              Upgrade to Team
            </Button>
            <Link href="/pricing" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
              Compare Plans
            </Link>
            <Link href="/contact" className={cn(buttonVariants({ variant: "ghost", size: "lg" }))}>
              Contact Sales
            </Link>
          </div>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="space-y-3"
      >
        <h2 className="text-lg font-semibold tracking-tight">Interactive preview</h2>
        <p className="text-sm text-muted-foreground">
          This is only a preview — unlock Team to run it on your real repositories.
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          <PreviewCodeCard
            title="Current Code"
            code={`@validator("name")\ndef validate(cls, v):\n    return v`}
          />
          <div className="flex flex-col">
            <div className="mb-2 hidden items-center justify-center text-muted-foreground lg:flex">
              <ArrowDown className="h-5 w-5" />
            </div>
            <PreviewCodeCard
              title="Suggested Code"
              code={`@field_validator("name")\ndef validate(cls, v):\n    return v`}
              accent
            />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={FileCode2} label="Affected Files" value="models.py" />
          <StatCard icon={Sparkles} label="Occurrences" value="3" />
          <StatCard icon={Timer} label="Estimated Time" value="2 minutes" />
          <StatCard icon={Check} label="Confidence" value="99%" />
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.14 }}
        className="grid gap-4 md:grid-cols-3"
      >
        {[
          {
            title: "Current → Updated",
            body: "Side-by-side diffs grounded in your repository AST — not generic release notes.",
          },
          {
            title: "Breaking APIs & patches",
            body: "Detect deprecated calls, generate patches when confidence is high, and plan the rest.",
          },
          {
            title: "Repo-wide upgrade plan",
            body: "File-level impact, estimated effort, and migration tasks your whole team can share.",
          },
        ].map((card, i) => (
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16 + i * 0.05 }}
            className="rounded-2xl border border-border/70 bg-card/50 p-5"
          >
            <h3 className="font-semibold tracking-tight">{card.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{card.body}</p>
          </motion.div>
        ))}
      </motion.section>

      <div className="rounded-2xl border border-primary/20 bg-primary/5 px-6 py-8 text-center">
        <h2 className="text-xl font-semibold">Ready to migrate with confidence?</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
          Team unlocks the flagship AI Migration Assistant for dependencies you track.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <Button onClick={openUpgrade}>Upgrade to Team</Button>
          <Link href="/pricing" className={cn(buttonVariants({ variant: "outline" }))}>
            Compare Plans
          </Link>
        </div>
      </div>
    </div>
  );
}

function PreviewCodeCard({
  title,
  code,
  accent,
}: {
  title: string;
  code: string;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border p-4",
        accent ? "border-primary/30 bg-primary/5" : "border-border/70 bg-secondary/40",
      )}
    >
      <div className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>
      <pre className="overflow-x-auto font-mono text-sm leading-relaxed">{code}</pre>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/50 px-4 py-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-1 font-mono text-lg font-semibold">{value}</div>
    </div>
  );
}
