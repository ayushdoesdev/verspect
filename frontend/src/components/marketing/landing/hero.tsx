"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ShieldAlert, Sparkles, Workflow } from "lucide-react";
import {
  CountUp,
  ProgressBar,
  TypewriterLines,
  WindowChrome,
} from "@/components/marketing/landing/primitives";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { PRICING_COPY } from "@/lib/evaluation-copy";

const terminalLines = [
  "verspect scan acme/payments-api --branch main",
  "✓ cloning repository",
  "✓ indexing 142 manifests · 1,840 AST nodes",
  "✓ security · 3 critical · 11 high",
  "✓ upgrade simulator · django 4.2 → 5.1",
  "✓ migration assistant · 18 patches ready",
];

export function LandingHero() {
  const reduce = useReducedMotion();
  const [scanProgress, setScanProgress] = useState(reduce ? 100 : 12);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => {
      setScanProgress((p) => {
        if (p >= 100) return 18;
        return Math.min(100, p + (p > 70 ? 3 : 7));
      });
    }, 380);
    return () => window.clearInterval(id);
  }, [reduce]);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => setPhase((p) => (p + 1) % 4), 3200);
    return () => window.clearInterval(id);
  }, [reduce]);

  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(61,214,198,0.10),transparent_55%)]" />
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage: "radial-gradient(ellipse at center, black 20%, transparent 75%)",
          }}
        />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-14 sm:px-6 sm:pt-20 lg:pb-24 lg:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col items-center gap-3"
          >
            <p className="font-[family-name:var(--font-display)] text-5xl font-semibold tracking-tight text-white sm:text-6xl lg:text-7xl">
              Verspect
            </p>
            <PrivateBetaBadge variant="marketing" className="text-[11px]" />
            <p className="max-w-md text-xs leading-relaxed text-slate-500">
              {PRICING_COPY.notice}
            </p>
          </motion.div>
          <motion.h1
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.08 }}
            className="mt-5 text-xl font-medium tracking-tight text-slate-100 sm:text-2xl lg:text-[1.75rem]"
          >
            Know every upgrade before you ship it.
          </motion.h1>
          <motion.p
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.14 }}
            className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-slate-400"
          >
            Scan repositories, simulate breaking changes, and generate exact migration
            patches — dependency intelligence for teams who refuse to guess.
          </motion.p>
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.2 }}
            className="mt-8 flex flex-wrap items-center justify-center gap-3"
          >
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-full bg-teal-400 px-6 py-3 text-sm font-semibold text-[#04201c] transition hover:bg-teal-300"
            >
              Start Evaluation <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="#scan-demo"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.03] px-6 py-3 text-sm font-medium text-white transition hover:bg-white/[0.07]"
            >
              See product demos
            </Link>
          </motion.div>
        </div>

        {/* Product stage — full-bleed interactive preview */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.28 }}
          className="relative mx-auto mt-14 max-w-5xl"
        >
          <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <WindowChrome
              title="verspect · live scan · acme/payments-api"
              trailing={
                <span className="rounded-full bg-teal-400/10 px-2 py-0.5 font-mono text-[10px] text-teal-300 ring-1 ring-teal-400/20">
                  scanning
                </span>
              }
            >
              <div className="grid gap-0 sm:grid-cols-[1fr_0.9fr]">
                <div className="border-b border-white/[0.06] p-4 sm:border-b-0 sm:border-r">
                  <TypewriterLines lines={terminalLines} lineDelay={650} />
                  <div className="mt-5">
                    <div className="mb-2 flex items-center justify-between text-[11px] text-slate-500">
                      <span>Repository index</span>
                      <span className="font-mono text-teal-300/90">{scanProgress}%</span>
                    </div>
                    <ProgressBar value={scanProgress} />
                  </div>
                </div>
                <div className="space-y-3 p-4">
                  <HeroMetric
                    icon={ShieldAlert}
                    label="Security findings"
                    value={14}
                    hint="3 critical · OSV matched"
                    active={phase === 0 || phase === 1}
                  />
                  <HeroMetric
                    icon={Workflow}
                    label="Upgrade risk"
                    value={72}
                    suffix="/100"
                    hint="django 4.2 → 5.1"
                    active={phase === 1 || phase === 2}
                  />
                  <HeroMetric
                    icon={Sparkles}
                    label="AI patches ready"
                    value={18}
                    hint="Team · Migration Assistant"
                    active={phase === 2 || phase === 3}
                  />
                </div>
              </div>
            </WindowChrome>

            <motion.div
              animate={reduce ? undefined : { y: [0, -8, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
              className="lg:pt-8"
            >
              <WindowChrome title="dashboard · repository health">
                <div className="space-y-4 p-4">
                  <div className="flex items-end justify-between">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Health score
                      </div>
                      <div className="mt-1 font-[family-name:var(--font-display)] text-4xl font-semibold text-white">
                        <CountUp value={86} />
                        <span className="text-lg text-slate-500">/100</span>
                      </div>
                    </div>
                    <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 font-mono text-[11px] text-emerald-300">
                      improving
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { label: "Deps", value: 248 },
                      { label: "Outdated", value: 37 },
                      { label: "CVEs", value: 14 },
                    ].map((m) => (
                      <div
                        key={m.label}
                        className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
                      >
                        <div className="text-[10px] uppercase tracking-wider text-slate-500">
                          {m.label}
                        </div>
                        <div className="mt-1 font-mono text-lg text-white">
                          <CountUp value={m.value} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <MiniBar label="Security" value={68} tone="rose" />
                    <MiniBar label="Freshness" value={74} tone="amber" />
                    <MiniBar label="Migration readiness" value={91} tone="teal" />
                  </div>
                </div>
              </WindowChrome>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function HeroMetric({
  icon: Icon,
  label,
  value,
  suffix = "",
  hint,
  active,
}: {
  icon: typeof ShieldAlert;
  label: string;
  value: number;
  suffix?: string;
  hint: string;
  active: boolean;
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-3 transition ${
        active
          ? "border-teal-400/30 bg-teal-400/[0.06]"
          : "border-white/[0.06] bg-white/[0.02]"
      }`}
    >
      <div className="flex items-center gap-2 text-[11px] text-slate-400">
        <Icon className={`h-3.5 w-3.5 ${active ? "text-teal-300" : "text-slate-500"}`} />
        {label}
      </div>
      <div className="mt-1 font-mono text-xl text-white">
        <CountUp value={value} />
        {suffix}
      </div>
      <div className="mt-0.5 text-[11px] text-slate-500">{hint}</div>
    </div>
  );
}

function MiniBar({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "teal" | "amber" | "rose";
}) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px] text-slate-500">
        <span>{label}</span>
        <span className="font-mono">{value}%</span>
      </div>
      <ProgressBar value={value} tone={tone} />
    </div>
  );
}
