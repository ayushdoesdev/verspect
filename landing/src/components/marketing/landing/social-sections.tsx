"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ChevronDown, ExternalLink } from "lucide-react";
import { FadeIn, Section } from "@/components/marketing/landing/primitives";

const repository = "https://github.com/ayushdoesdev/verspect";
const faqs = [
  { q: "What is Verspect?", a: "Verspect is a dependency intelligence tool for GitHub repositories. It helps you inspect dependency inventory and usage, identify vulnerability and license signals, understand package health, explore dependency relationships, and evaluate upgrade impact." },
  { q: "Is Verspect open source?", a: "Yes. The current main-branch project source is licensed under Apache-2.0. The earlier v0.1.0-beta.1 release remains under AGPL-3.0-or-later, and third-party dependencies retain their own licenses and notices." },
  { q: "Is Verspect a hosted service?", a: "No official hosted SaaS service is currently provided. Verspect is self-hosted, so you run and manage the application on infrastructure you control. Docker Compose is the recommended setup." },
  { q: "How do I install Verspect?", a: "Follow the Docker Compose quick-start in the GitHub repository. The application is self-hosted and requires the services described in its installation documentation." },
  { q: "Which ecosystems are supported?", a: "The scanner supports Python, JavaScript and TypeScript, Go, Java, Rust, PHP, and Ruby. Analysis depth varies by ecosystem and by the manifests, lockfiles, and source evidence available." },
  { q: "Do all ecosystems have the same analysis depth?", a: "No. Python has the deepest deterministic usage and migration analysis. Other ecosystems provide varying levels of dependency inventory, import or module usage, vulnerability, license, and package-health analysis. Advanced language-specific breaking-change analysis is more limited outside the strongest supported Python package rules." },
  { q: "Does Verspect require an AI provider?", a: "No. AI integrations are optional. Deterministic dependency, security, license, and upgrade-analysis capabilities can be used without configuring an AI provider. AI-assisted migration suggestions require a configured provider." },
  { q: "How does vulnerability detection work?", a: "Verspect matches detected package names and versions against OSV vulnerability data. Results depend on package identification, available version evidence, and upstream advisory coverage. A scan should not be treated as a guarantee that a repository has no vulnerabilities." },
  { q: "Can Verspect automatically create GitHub pull requests?", a: "Migration suggestions and patch drafts can be reviewed in the application. Creating a pull request requires reviewing the proposed change and explicitly confirming the action; unattended automatic pull requests are not enabled." },
  { q: "Are the landing-page demonstrations live scans?", a: "No. The animated terminal, scan pipeline, simulator, migration diff, dependency graph, and dashboard use illustrative example data. They do not scan a visitor's repository or connect to the Verspect backend." },
  { q: "Can I contribute to Verspect?", a: "Yes. The source is public on GitHub. Read CONTRIBUTING.md for contribution guidance, or use the repository's Issues page to report a problem or suggest an improvement." },
];

export function RoadmapTeaserSection() {
  return (
    <section id="community" className="relative border-t border-white/[0.06] py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <FadeIn>
          <div className="rounded-3xl border border-teal-400/20 bg-gradient-to-br from-teal-400/10 via-transparent to-sky-500/10 p-8 sm:p-12">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-teal-300/80">Open source · Built in the open</p>
            <h2 className="mt-3 max-w-2xl font-[family-name:var(--font-display)] text-3xl font-semibold text-white">Explore the project. Follow its progress. Help shape what comes next.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-400">Browse the source, follow releases, report issues, and contribute improvements. Project changes are tracked publicly.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href={`${repository}/issues`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-2 rounded-full bg-teal-400 px-5 py-2.5 text-sm font-semibold text-[#04201c] transition hover:bg-teal-300">Issues & feedback <ExternalLink className="h-4 w-4" /></a>
              <a href={`${repository}/releases`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-white/[0.05]">View releases <ExternalLink className="h-4 w-4" /></a>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

export function FaqSection() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <Section id="faq" eyebrow="FAQ" title="Answers about the project, without the sales pitch.">
      <div className="mx-auto max-w-3xl space-y-2">
        {faqs.map((faq, index) => {
          const isOpen = open === index;
          const answerId = `verspect-faq-answer-${index}`;
          return (
            <FadeIn key={faq.q} delay={index * 0.025}>
              <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.02]">
                <button type="button" className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left" onClick={() => setOpen(isOpen ? null : index)} aria-expanded={isOpen} aria-controls={answerId}>
                  <span className="text-sm font-medium text-white sm:text-base">{faq.q}</span>
                  <ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && <motion.div id={answerId} initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }}>
                    <p className="px-5 pb-4 text-sm leading-relaxed text-slate-400">{faq.a}</p>
                  </motion.div>}
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
          <p className="font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-white sm:text-5xl">Verspect</p>
          <h2 className="mt-4 text-xl font-medium text-slate-100 sm:text-2xl">Understand your dependencies before the next upgrade.</h2>
          <p className="mx-auto mt-4 max-w-lg text-slate-400">Explore the source, read the installation guide, and run Verspect on infrastructure you control.</p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a href={repository} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-2 rounded-full bg-teal-400 px-6 py-3 text-sm font-semibold text-[#04201c] transition hover:bg-teal-300">View on GitHub <ArrowRight className="h-4 w-4" /></a>
            <a href={`${repository}#quick-start-with-docker-compose`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-3 text-sm text-white transition hover:bg-white/[0.05]">Installation guide <ArrowRight className="h-4 w-4" /></a>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
