"use client";

import { motion } from "framer-motion";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { ROADMAP } from "@/lib/roadmap-data";

const columns = [
  { key: "planned" as const, title: "Planned", accent: "border-slate-500/40 text-slate-300" },
  {
    key: "in_progress" as const,
    title: "In Progress",
    accent: "border-teal-400/40 text-teal-200",
  },
  { key: "released" as const, title: "Released", accent: "border-sky-400/40 text-sky-200" },
];

export default function RoadmapPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <section className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-[radial-gradient(ellipse_at_top,rgba(61,214,198,0.10),transparent_65%)]" />
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative mb-3 flex flex-wrap items-center gap-3"
        >
          <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold text-white">
            Roadmap
          </h1>
          <PrivateBetaBadge variant="marketing" />
        </motion.div>
        <p className="relative mb-12 max-w-2xl text-slate-400">
          Where Verspect is headed during Private Beta — Planned, In Progress, and Released.
        </p>

        <div className="relative grid gap-4 lg:grid-cols-3">
          {columns.map((col, colIndex) => (
            <motion.div
              key={col.key}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: colIndex * 0.05 }}
              className={`rounded-2xl border bg-white/[0.03] p-4 ${col.accent}`}
            >
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider">{col.title}</h2>
              <div className="space-y-3">
                {ROADMAP[col.key].map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-white/10 bg-[#0c1117]/80 px-3.5 py-3"
                  >
                    <div className="text-sm font-medium text-white">{item.title}</div>
                    {item.description ? (
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">
                        {item.description}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </section>
      <MarketingFooter />
    </div>
  );
}
