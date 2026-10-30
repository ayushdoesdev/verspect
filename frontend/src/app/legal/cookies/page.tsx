import type { Metadata } from "next";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";

export const metadata: Metadata = {
  title: "Cookie Policy — Dependency Intelligence",
};

export default function CookiesPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <article className="prose prose-invert mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1>Cookie Policy</h1>
        <p>Last updated: August 1, 2026</p>
        <p>
          We use essential cookies for authentication and session security, and optional analytics
          cookies to understand product usage. You can control non-essential cookies in your browser
          settings.
        </p>
        <h2>Categories</h2>
        <ul>
          <li>Essential — login sessions, CSRF protection, preference storage</li>
          <li>Analytics — aggregated product usage (when enabled)</li>
          <li>Marketing — not used for third-party advertising today</li>
        </ul>
      </article>
      <MarketingFooter />
    </div>
  );
}
