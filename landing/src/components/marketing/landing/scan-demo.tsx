"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Check,
  GitBranch,
  Loader2,
  PackageSearch,
  ShieldAlert,
  Workflow,
} from "lucide-react";
import {
  FadeIn,
  ProgressBar,
  Section,
  SkeletonPulse,
  WindowChrome,
} from "@/components/marketing/landing/primitives";

const steps = [
  {
    id: "import",
    title: "GitHub import",
    detail: "oauth · acme/payments-api · main",
    icon: GitBranch,
  },
  {
    id: "index",
    title: "Repository indexing",
    detail: "pyproject.toml · requirements · 184 source files",
    icon: PackageSearch,
  },
  {
    id: "deps",
    title: "Dependency detection",
    detail: "248 packages · 1,840 AST call sites",
    icon: PackageSearch,
  },
  {
    id: "security",
    title: "Security analysis",
    detail: "OSV + advisories mapped to installed versions",
    icon: ShieldAlert,
  },
  {
    id: "upgrade",
    title: "Upgrade analysis",
    detail: "Breaking APIs · migration effort · health score",
    icon: Workflow,
  },
];

const detected = [
  { name: "django", from: "4.2.11", to: "5.1.4", risk: "high" },
  { name: "requests", from: "2.31.0", to: "2.32.3", risk: "low" },
  { name: "pydantic", from: "1.10.13", to: "2.10.3", risk: "high" },
  { name: "celery", from: "5.3.6", to: "5.4.1", risk: "med" },
];

export function ScanDemoSection() {
  const reduce = useReducedMotion();
  const [active, setActive] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (reduce) {
      setActive(steps.length - 1);
      setProgress(100);
      return;
    }
    const id = window.setInterval(() => {
      setActive((i) => {
        const next = (i + 1) % steps.length;
        setProgress(((next + 1) / steps.length) * 100);
        return next;
      });
    }, 2200);
    setProgress(((active + 1) / steps.length) * 100);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduce]);

  return (
    <Section
      id="scan-demo"
      eyebrow="Repository Scan"
      title="Watch a full scan unfold."
      description="An illustrative walkthrough of repository discovery, dependency indexing, security enrichment, and upgrade analysis. No live repository is scanned on this page."
    >
      <div className="grid items-start gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <FadeIn>
          <ol className="space-y-2">
            {steps.map((step, idx) => {
              const done = idx < active;
              const current = idx === active;
              const Icon = step.icon;
              return (
                <li
                  key={step.id}
                  className={`flex gap-3 rounded-xl border px-4 py-3 transition ${
                    current
                      ? "border-teal-400/35 bg-teal-400/[0.07]"
                      : done
                        ? "border-white/[0.06] bg-white/[0.02]"
                        : "border-transparent bg-transparent opacity-50"
                  }`}
                >
                  <div
                    className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                      current
                        ? "bg-teal-400/15 text-teal-300"
                        : done
                          ? "bg-emerald-400/10 text-emerald-300"
                          : "bg-white/5 text-slate-500"
                    }`}
                  >
                    {done ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : current ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Icon className="h-3.5 w-3.5" />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white">{step.title}</div>
                    <div className="mt-0.5 font-mono text-[11px] text-slate-500">
                      {step.detail}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </FadeIn>

        <FadeIn delay={0.08}>
          <WindowChrome
            title="scan pipeline · payments-api"
            trailing={
              <span className="font-mono text-[10px] text-slate-500">
                {Math.round(progress)}%
              </span>
            }
          >
            <div className="p-4">
              <ProgressBar value={progress} className="mb-4" />
              <AnimatePresence mode="wait">
                <motion.div
                  key={active}
                  initial={reduce ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduce ? undefined : { opacity: 0, y: -8 }}
                  transition={{ duration: 0.3 }}
                >
                  {active <= 1 && (
                    <div className="space-y-2">
                      <SkeletonPulse className="h-3 w-2/3" />
                      <SkeletonPulse className="h-3 w-1/2" />
                      <SkeletonPulse className="h-24 w-full" />
                      <div className="grid grid-cols-3 gap-2 pt-2">
                        <SkeletonPulse className="h-14" />
                        <SkeletonPulse className="h-14" />
                        <SkeletonPulse className="h-14" />
                      </div>
                    </div>
                  )}
                  {active >= 2 && (
                    <div className="space-y-2">
                      {detected.map((dep, i) => (
                        <motion.div
                          key={dep.name}
                          initial={reduce ? false : { opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.06 }}
                          className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
                        >
                          <div>
                            <div className="font-mono text-sm text-white">{dep.name}</div>
                            <div className="font-mono text-[11px] text-slate-500">
                              {dep.from} → {dep.to}
                            </div>
                          </div>
                          <RiskPill risk={dep.risk} />
                        </motion.div>
                      ))}
                      {active >= 3 && (
                        <div className="mt-3 grid grid-cols-3 gap-2">
                          {[
                            { label: "Critical", value: "3", tone: "text-rose-300" },
                            { label: "High", value: "11", tone: "text-amber-300" },
                            { label: "Breaking APIs", value: "9", tone: "text-teal-300" },
                          ].map((s) => (
                            <div
                              key={s.label}
                              className="rounded-lg border border-white/[0.06] bg-[#0c131c] px-3 py-2"
                            >
                              <div className="text-[10px] uppercase tracking-wider text-slate-500">
                                {s.label}
                              </div>
                              <div className={`mt-1 font-mono text-lg ${s.tone}`}>
                                {s.value}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </WindowChrome>
        </FadeIn>
      </div>
    </Section>
  );
}

function RiskPill({ risk }: { risk: string }) {
  const styles =
    risk === "high"
      ? "bg-rose-400/10 text-rose-300 ring-rose-400/20"
      : risk === "med"
        ? "bg-amber-400/10 text-amber-300 ring-amber-400/20"
        : "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20";
  return (
    <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] ring-1 ${styles}`}>
      {risk}
    </span>
  );
}
