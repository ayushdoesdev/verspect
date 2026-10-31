"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  FadeIn,
  ProgressBar,
  Section,
  WindowChrome,
} from "@/components/marketing/landing/primitives";

const versions = ["4.2.11", "5.0.9", "5.1.4"];

const findings = [
  { api: "django.conf.urls.url", severity: "breaking", files: 12 },
  { api: "ugettext_lazy", severity: "breaking", files: 7 },
  { api: "FORCE_SCRIPT_NAME default", severity: "warning", files: 3 },
  { api: "DEFAULT_AUTO_FIELD", severity: "info", files: 1 },
];

export function SimulatorDemoSection() {
  const reduce = useReducedMotion();
  const [targetIdx, setTargetIdx] = useState(2);
  const [risk, setRisk] = useState(reduce ? 72 : 0);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => {
      setPhase((p) => (p + 1) % 5);
      setTargetIdx((i) => (i === 2 ? 1 : 2));
    }, 2800);
    return () => window.clearInterval(id);
  }, [reduce]);

  useEffect(() => {
    const next = targetIdx === 2 ? 72 : 48;
    if (reduce) {
      setRisk(next);
      return;
    }
    setRisk(0);
    const t = window.setTimeout(() => setRisk(next), 120);
    return () => window.clearTimeout(t);
  }, [targetIdx, reduce]);

  const bars = useMemo(
    () => [
      { label: "API breaks", value: targetIdx === 2 ? 68 : 42, tone: "rose" as const },
      { label: "File impact", value: targetIdx === 2 ? 54 : 31, tone: "amber" as const },
      { label: "Effort", value: targetIdx === 2 ? 61 : 38, tone: "sky" as const },
      { label: "Confidence", value: 88, tone: "teal" as const },
    ],
    [targetIdx],
  );

  return (
    <Section
      id="simulator"
      eyebrow="Upgrade Simulator"
      title="Simulate the bump before you touch a pin."
      description="Select a target version and explore example findings, impact indicators, and migration considerations. This is an illustrative simulation, not a live compatibility assessment."
    >
      <FadeIn>
        <WindowChrome
          title="upgrade simulator · django"
          trailing={
            <span className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400 ring-1 ring-white/10">
              analysis
            </span>
          }
        >
          <div className="grid gap-0 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="space-y-5 border-b border-white/[0.06] p-5 lg:border-b-0 lg:border-r">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-slate-500">
                  Version selection
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-xs text-slate-400">
                    current 4.2.11
                  </span>
                  {versions.slice(1).map((v, i) => {
                    const selected = targetIdx === i + 1;
                    return (
                      <button
                        key={v}
                        type="button"
                        onClick={() => setTargetIdx(i + 1)}
                        className={`rounded-lg border px-3 py-1.5 font-mono text-xs transition ${
                          selected
                            ? "border-teal-400/40 bg-teal-400/10 text-teal-200"
                            : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20"
                        }`}
                      >
                        → {v}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[11px] uppercase tracking-wider text-slate-500">
                    Risk calculation
                  </span>
                  <motion.span
                    key={risk}
                    initial={reduce ? false : { opacity: 0.4 }}
                    animate={{ opacity: 1 }}
                    className="font-mono text-sm text-amber-300"
                  >
                    {risk}/100
                  </motion.span>
                </div>
                <ProgressBar value={risk} tone="amber" />
              </div>

              <div>
                <div className="mb-3 text-[11px] uppercase tracking-wider text-slate-500">
                  Impact charts
                </div>
                <div className="space-y-3">
                  {bars.map((b) => (
                    <div key={b.label}>
                      <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                        <span>{b.label}</span>
                        <span className="font-mono">{b.value}%</span>
                      </div>
                      <ProgressBar value={b.value} tone={b.tone} />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-wider text-slate-500">
                  Breaking API detection
                </div>
                <div className="font-mono text-[11px] text-slate-500">
                  phase {phase + 1}/5
                </div>
              </div>
              <div className="space-y-2">
                {findings.map((f, i) => (
                  <motion.div
                    key={f.api}
                    initial={reduce ? false : { opacity: 0.35, x: -6 }}
                    animate={{
                      opacity: i <= phase + 1 ? 1 : 0.35,
                      x: 0,
                      borderColor:
                        i === phase
                          ? "rgba(61,214,198,0.35)"
                          : "rgba(255,255,255,0.06)",
                    }}
                    className="rounded-lg border bg-white/[0.02] px-3 py-2.5"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <code className="truncate font-mono text-[12px] text-slate-200">
                        {f.api}
                      </code>
                      <Severity severity={f.severity} />
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">
                      {f.files} affected files
                    </div>
                  </motion.div>
                ))}
              </div>

              <motion.div
                animate={{
                  opacity: phase >= 3 ? 1 : 0.45,
                }}
                className="mt-4 rounded-xl border border-teal-400/20 bg-teal-400/[0.05] p-4"
              >
                <div className="text-[11px] uppercase tracking-wider text-teal-300/80">
                  Migration summary
                </div>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">
                  {targetIdx === 2
                    ? "9 breaking APIs across 28 files. Estimated effort: 2–3 engineer days. Suggested patches available for 18 call sites."
                    : "4 breaking APIs across 11 files. Intermediate hop recommended before 5.1."}
                </p>
              </motion.div>
            </div>
          </div>
        </WindowChrome>
      </FadeIn>
    </Section>
  );
}

function Severity({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    breaking: "bg-rose-400/10 text-rose-300 ring-rose-400/20",
    warning: "bg-amber-400/10 text-amber-300 ring-amber-400/20",
    info: "bg-sky-400/10 text-sky-300 ring-sky-400/20",
  };
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] ring-1 ${map[severity] || map.info}`}
    >
      {severity}
    </span>
  );
}
