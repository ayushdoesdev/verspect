"use client";

import Link from "next/link";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";

const sections = [
  {
    title: "Supported languages",
    body: "Python, JavaScript, TypeScript, Go, Java, Rust, PHP, and Ruby. Package managers and analysis limits are listed in the repository docs (docs/languages.md).",
  },
  {
    title: "Scanning",
    body: "Connect GitHub, import a repository, and run a scan. Verspect parses manifests and lockfiles, records usage, queries OSV, detects licenses, and scores health from observed signals only.",
  },
  {
    title: "Upgrade impact",
    body: "Upgrade Simulator compares used APIs against deterministic catalogs where they exist. Missing catalog matches are unresolved, not automatically breaking. A major version bump is not treated as breaking by itself.",
  },
  {
    title: "Migration and GitHub PRs",
    body: "Team plan can generate patches. Creating a GitHub pull request requires an explicit confirm in the UI and API. Verspect does not open PRs unattended.",
  },
  {
    title: "Billing",
    body: "Evaluation, Starter, Pro, and Team are self-serve when Stripe or Razorpay is configured. Limits are enforced on the server. Enterprise SSO/SCIM is not self-serve in the product today.",
  },
];

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <section className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold text-white">Documentation</h1>
        <p className="mt-4 text-slate-400">
          In-app overview of capabilities that ship today. Operators should also read the repository docs for environment variables, security, and testing.
        </p>
        <div className="mt-10 space-y-6">
          {sections.map((section) => (
            <article key={section.title} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
              <h2 className="text-lg font-semibold text-white">{section.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{section.body}</p>
            </article>
          ))}
        </div>
        <ul className="mt-10 space-y-3 text-sm text-slate-300">
          <li>
            <Link className="text-teal-300 hover:underline" href="/onboarding">
              Getting started / onboarding
            </Link>
          </li>
          <li>
            <Link className="text-teal-300 hover:underline" href="/pricing">
              Plans & limits
            </Link>
          </li>
          <li>
            <Link className="text-teal-300 hover:underline" href="/roadmap">
              Public roadmap
            </Link>
          </li>
        </ul>
      </section>
      <MarketingFooter />
    </div>
  );
}
