"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, ChevronDown, Quote } from "lucide-react";
import { FadeIn, Section } from "@/components/marketing/landing/primitives";

const testimonials = [
  {
    quote:
      "We stopped treating Django upgrades like fire drills. The simulator showed exactly which call sites would break.",
    name: "Engineering lead",
    role: "Platform · Series B SaaS",
    placeholder: true,
  },
  {
    quote:
      "Security findings finally mapped to the versions we actually ship — not a generic CVE dump.",
    name: "Security engineer",
    role: "Fintech · SOC2 team",
    placeholder: true,
  },
  {
    quote:
      "Migration Assistant patches were close enough that junior engineers could land the PR the same afternoon.",
    name: "Staff engineer",
    role: "Marketplace · Python monorepo",
    placeholder: true,
  },
];

const faqs = [
  {
    q: "What do I get during the Evaluation?",
    a: "Evaluation Plan is perfect for evaluating Verspect on your repositories before upgrading to a paid plan. You get 7 days of write access with scanning, dependency graph, security analysis, and Upgrade Simulator — no credit card. AI-powered capabilities are available on eligible paid plans. When evaluation expires, the workspace becomes read-only until you upgrade.",
  },
  {
    q: "Is Upgrade Simulator the same as AI Migration Assistant?",
    a: "No. Upgrade Simulator is deterministic analysis (available on Evaluation and paid plans). AI Migration Assistant generates exact code patches and is Team / Enterprise only.",
  },
  {
    q: "Which languages are supported today?",
    a: "Python, JavaScript, TypeScript, Go, Java, Rust, PHP, and Ruby are scanned today. Deterministic breaking-change catalogs are deepest for selected Python packages (pydantic, numpy, FastAPI, Flask, Django). Other languages get import/module usage, versions, OSV, licenses, and health — not fabricated API-level analysis.",
  },
  {
    q: "Can we run Verspect with our own AI keys?",
    a: "Yes. Configure your preferred LLM provider in settings. Enterprise can use private AI deployments.",
  },
  {
    q: "Do you generate pull requests yet?",
    a: "Suggested patches ship today. You can create a GitHub pull request after reviewing the diff — only with an explicit confirm. Unattended automatic PRs are not enabled.",
  },
];

const aiRoadmapItems = [
  "Automatic migration fixes",
  "Unattended automatic pull requests",
  "Repository chat",
  "Upgrade planning agents",
  "Technical debt prediction",
  "Dependency recommendations",
];

/** Restored from the previous landing — teaser that links to the full Roadmap page. */
export function RoadmapTeaserSection() {
  return (
    <section id="roadmap" className="relative border-t border-white/[0.06] py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <FadeIn>
          <div className="rounded-3xl border border-teal-400/20 bg-gradient-to-br from-teal-400/10 via-transparent to-sky-500/10 p-8 sm:p-12">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-teal-300/80">
              AI Roadmap
            </p>
            <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold text-white">
              Coming next: automatic fixes, PRs, and repository chat.
            </h2>
            <ul className="mt-6 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
              {aiRoadmapItems.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-300" />
                  {item}
                </li>
              ))}
            </ul>
            <Link
              href="/roadmap"
              className="mt-8 inline-flex items-center gap-2 text-sm font-medium text-teal-300 transition hover:text-teal-200"
            >
              View full roadmap <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

export function TestimonialsSection() {
  return (
    <Section
      id="testimonials"
      eyebrow="Customers"
      title="Built with teams who ship carefully."
      description="Placeholders for launch — swap in real quotes as design partners go live."
    >
      <div className="grid gap-4 md:grid-cols-3">
        {testimonials.map((t, i) => (
          <FadeIn key={t.name} delay={i * 0.06}>
            <figure className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-5">
              <Quote className="h-4 w-4 text-teal-300/70" />
              <blockquote className="mt-3 flex-1 text-sm leading-relaxed text-slate-300">
                “{t.quote}”
              </blockquote>
              <figcaption className="mt-5 border-t border-white/[0.06] pt-4">
                <div className="text-sm font-medium text-white">{t.name}</div>
                <div className="text-xs text-slate-500">{t.role}</div>
                {t.placeholder && (
                  <div className="mt-2 font-mono text-[10px] uppercase tracking-wider text-slate-600">
                    Placeholder
                  </div>
                )}
              </figcaption>
            </figure>
          </FadeIn>
        ))}
      </div>
    </Section>
  );
}

export function FaqSection() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <Section id="faq" eyebrow="FAQ" title="Answers before you sign up.">
      <div className="mx-auto max-w-3xl space-y-2">
        {faqs.map((f, i) => {
          const isOpen = open === i;
          return (
            <FadeIn key={f.q} delay={i * 0.03}>
              <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.02]">
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                >
                  <span className="text-sm font-medium text-white sm:text-base">{f.q}</span>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-slate-500 transition ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                    >
                      <p className="px-5 pb-4 text-sm leading-relaxed text-slate-400">
                        {f.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </FadeIn>
          );
        })}
      </div>
    </Section>
  );
}

export function FinalCtaSection() {
  return (
    <section className="relative overflow-hidden border-t border-white/[0.06] py-24">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(61,214,198,0.10),transparent_60%)]" />
      <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6">
        <FadeIn>
          <p className="font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Verspect
          </p>
          <h2 className="mt-4 text-xl font-medium text-slate-100 sm:text-2xl">
            Stop guessing. Start scanning.
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-slate-400">
            Import a repository in minutes. See security, upgrades, and migrations
            before the next deploy.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-full bg-teal-400 px-6 py-3 text-sm font-semibold text-[#04201c] transition hover:bg-teal-300"
            >
              Start Evaluation <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-3 text-sm text-white transition hover:bg-white/[0.05]"
            >
              Request Demo
            </Link>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
