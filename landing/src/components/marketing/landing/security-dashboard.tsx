"use client";

import { motion } from "framer-motion";
import {
  CountUp,
  FadeIn,
  ProgressBar,
  Section,
  WindowChrome,
} from "@/components/marketing/landing/primitives";

const severities = [
  {
    label: "Critical",
    count: 3,
    tone: "rose" as const,
    examples: ["CVE-2024-27304 · django", "CVE-2023-32681 · requests"],
  },
  {
    label: "High",
    count: 11,
    tone: "amber" as const,
    examples: ["GHSA-xxx · urllib3", "OSV · pydantic < 2.4"],
  },
  {
    label: "Medium",
    count: 27,
    tone: "sky" as const,
    examples: ["outdated transitive pins", "license policy warnings"],
  },
  {
    label: "Low",
    count: 48,
    tone: "teal" as const,
    examples: ["informational advisories", "non-blocking bumps"],
  },
];

export function SecurityDashboardSection() {
  return (
    <Section
      id="security"
      eyebrow="Security Dashboard"
      title="Security intelligence tied to installed versions."
      description="An illustrative security dashboard with animated severity counts and sample advisory matches. Values are examples, not findings from a live repository."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {severities.map((s, i) => (
          <FadeIn key={s.label} delay={i * 0.05}>
            <motion.div
              whileHover={{ y: -3 }}
              transition={{ duration: 0.2 }}
              className="rounded-2xl border border-white/10 bg-white/[0.02] p-5"
            >
              <div className="text-[11px] uppercase tracking-wider text-slate-500">
                {s.label}
              </div>
              <div
                className={`mt-2 font-[family-name:var(--font-display)] text-4xl font-semibold ${
                  s.tone === "rose"
                    ? "text-rose-300"
                    : s.tone === "amber"
                      ? "text-amber-300"
                      : s.tone === "sky"
                        ? "text-sky-300"
                        : "text-teal-300"
                }`}
              >
                <CountUp value={s.count} />
              </div>
              <ProgressBar
                value={Math.min(100, s.count * (s.tone === "rose" ? 18 : 3))}
                tone={s.tone === "sky" ? "sky" : s.tone}
                className="mt-4"
              />
              <ul className="mt-4 space-y-1.5">
                {s.examples.map((ex) => (
                  <li key={ex} className="truncate font-mono text-[11px] text-slate-500">
                    {ex}
                  </li>
                ))}
              </ul>
            </motion.div>
          </FadeIn>
        ))}
      </div>

      <FadeIn delay={0.1} className="mt-6">
        <WindowChrome title="security · repository rollup">
          <div className="grid gap-4 p-5 sm:grid-cols-3">
            {[
              { label: "Packages scanned", value: 248 },
              { label: "Advisories matched", value: 89 },
              { label: "Fixable this week", value: 22 },
            ].map((m) => (
              <div
                key={m.label}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-4"
              >
                <div className="text-[11px] uppercase tracking-wider text-slate-500">
                  {m.label}
                </div>
                <div className="mt-2 font-mono text-3xl text-white">
                  <CountUp value={m.value} />
                </div>
              </div>
            ))}
          </div>
        </WindowChrome>
      </FadeIn>
    </Section>
  );
}
