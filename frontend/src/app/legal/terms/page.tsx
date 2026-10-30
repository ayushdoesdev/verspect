import type { Metadata } from "next";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";

export const metadata: Metadata = {
  title: "Terms of Service — Dependency Intelligence",
  description: "Terms governing use of the Dependency Intelligence platform.",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <article className="prose prose-invert mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1>Terms of Service</h1>
        <p>Last updated: August 1, 2026</p>
        <p>
          By accessing Dependency Intelligence you agree to these Terms. If you use the service on
          behalf of an organization, you represent that you have authority to bind that organization.
        </p>
        <h2>Accounts &amp; organizations</h2>
        <p>
          You are responsible for credentials, invited members, and activity under your organization.
          Plan limits (repositories, seats, AI features) are enforced according to your subscription.
        </p>
        <h2>Acceptable use</h2>
        <p>
          You may only scan repositories you are authorized to access. You may not probe, reverse
          engineer, or abuse the service, or use it to violate applicable law.
        </p>
        <h2>Subscriptions</h2>
        <p>
          Paid plans renew until canceled. Trials convert to paid unless canceled. Fees are handled
          by Stripe; taxes may apply. Downgrades take effect at period end unless otherwise stated.
        </p>
        <h2>Disclaimer</h2>
        <p>
          Upgrade and security intelligence is advisory. You remain responsible for validating
          changes in your environments before production deployment.
        </p>
        <h2>Contact</h2>
        <p>legal@dependencyintelligence.dev</p>
      </article>
      <MarketingFooter />
    </div>
  );
}
