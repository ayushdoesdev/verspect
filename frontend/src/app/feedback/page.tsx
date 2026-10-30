"use client";

import Link from "next/link";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { FeedbackForm } from "@/components/feedback/feedback-form";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";

/** Public marketing Feedback Center — never uses the customer AppShell. */
export default function FeedbackPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />

      <section className="relative overflow-hidden border-b border-white/10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(61,214,198,0.12),transparent_55%)]" />
        <div className="relative mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 sm:py-20">
          <div className="mb-4 flex justify-center">
            <PrivateBetaBadge variant="marketing" />
          </div>
          <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Feedback
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-slate-400">
            Help us build the best Dependency Intelligence Platform. Every submission is reviewed
            by the Verspect team.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-4 py-12 sm:px-6 sm:py-16">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 sm:p-8 [&_.text-muted-foreground]:text-slate-400">
          <FeedbackForm />
        </div>

        <div className="mt-12 space-y-10 text-sm [&_a]:text-teal-300">
          <section>
            <h2 className="text-base font-semibold tracking-tight text-white">
              What happens next?
            </h2>
            <ul className="mt-3 space-y-2 text-slate-400">
              <li>✓ Every submission is reviewed.</li>
              <li>✓ Critical bugs are prioritized.</li>
              <li>✓ Feature requests help shape the roadmap.</li>
              <li>✓ We may contact you for additional information.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold tracking-tight text-white">
              Before submitting
            </h2>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-slate-400">
              <li>
                Search the <Link href="/roadmap">Roadmap</Link> first.
              </li>
              <li>
                Search the <Link href="/changelog">Changelog</Link>.
              </li>
              <li>Include reproduction steps for bugs.</li>
              <li>Do not include passwords, tokens, secrets or confidential source code.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold tracking-tight text-white">Privacy</h2>
            <p className="mt-2 text-slate-400">
              Your feedback is only used for improving Verspect.
            </p>
            <p className="mt-1 text-slate-400">We never sell your information.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold tracking-tight text-white">Terms</h2>
            <p className="mt-2 text-slate-400">By submitting feedback you agree:</p>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-slate-400">
              <li>We may contact you regarding your submission.</li>
              <li>Suggestions may be incorporated into Verspect.</li>
              <li>Do not submit confidential source code.</li>
              <li>Feedback may be used to improve the platform.</li>
            </ul>
          </section>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
