import type { Metadata } from "next";
import Link from "next/link";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";

export const metadata: Metadata = {
  title: "Privacy Policy — Dependency Intelligence",
  description: "How Dependency Intelligence collects, uses, and protects your data.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <article className="prose prose-invert mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1>Privacy Policy</h1>
        <p>Last updated: August 1, 2026</p>
        <p>
          Dependency Intelligence (&quot;we&quot;, &quot;us&quot;) provides dependency scanning and upgrade
          intelligence for software teams. This policy explains what we collect and why.
        </p>
        <h2>Information we collect</h2>
        <ul>
          <li>Account information (name, email, authentication provider identifiers)</li>
          <li>Repository metadata and dependency manifests you authorize us to scan</li>
          <li>Usage and billing information required to operate subscriptions</li>
          <li>Technical logs needed for security and reliability</li>
        </ul>
        <h2>How we use information</h2>
        <p>
          We use data to provide scanning, vulnerability analysis, migration intelligence, billing,
          support, and product improvement. We do not sell personal data.
        </p>
        <h2>Sharing</h2>
        <p>
          We share data with subprocessors required to operate the service (hosting, email, payments
          via Stripe, and LLM providers you configure). Access is limited to what is necessary.
        </p>
        <h2>Retention &amp; security</h2>
        <p>
          We retain account and scan data while your account is active and for a reasonable period
          afterward for backups and legal obligations. We apply industry-standard encryption in
          transit and access controls at rest.
        </p>
        <h2>Your rights</h2>
        <p>
          You may request access, correction, or deletion of your personal data by contacting{" "}
          <Link href="/contact">support</Link>.
        </p>
        <h2>Contact</h2>
        <p>privacy@dependencyintelligence.dev</p>
      </article>
      <MarketingFooter />
    </div>
  );
}
