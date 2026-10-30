"use client";

import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { CHANGELOG } from "@/lib/changelog";

export default function ChangelogPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <section className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <div className="mb-3 flex items-center gap-2">
          <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold text-white">
            Changelog
          </h1>
          <PrivateBetaBadge variant="marketing" />
        </div>
        <p className="mb-12 max-w-xl text-slate-400">
          What shipped in Verspect — newest first.
        </p>
        <div className="space-y-10">
          {CHANGELOG.map((entry) => (
            <article
              key={entry.version}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"
            >
              <div className="flex flex-wrap items-baseline gap-3">
                <h2 className="text-lg font-semibold text-white">v{entry.version}</h2>
                <time className="text-xs text-slate-500">{entry.date}</time>
              </div>
              <ul className="mt-4 space-y-2 text-sm text-slate-300">
                {entry.changes.map((change) => (
                  <li key={change} className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400" />
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>
      <MarketingFooter />
    </div>
  );
}
