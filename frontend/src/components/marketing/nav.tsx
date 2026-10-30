"use client";

import Link from "next/link";
import { useState } from "react";
import { Activity, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";

const links = [
  { href: "/#scan-demo", label: "Product" },
  { href: "/#simulator", label: "Simulator" },
  { href: "/#migration", label: "Migration" },
  { href: "/pricing", label: "Pricing" },
  { href: "/roadmap", label: "Roadmap" },
  { href: "/changelog", label: "Changelog" },
  { href: "/feedback", label: "Feedback" },
  { href: "/contact", label: "Contact" },
  { href: "/docs", label: "Docs" },
];

export function MarketingNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#070b12]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-400/15 text-teal-300 ring-1 ring-teal-400/30">
            <Activity className="h-5 w-5" />
          </span>
          <span className="font-[family-name:var(--font-display)] text-sm font-semibold tracking-tight text-white sm:text-base">
            Verspect
          </span>
          <PrivateBetaBadge variant="marketing" />
        </Link>
        <nav className="hidden items-center gap-7 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-sm text-slate-400 transition hover:text-white"
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-3 md:flex">
          <Link href="/login" className="text-sm text-slate-300 hover:text-white">
            Sign In
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-teal-400 px-4 py-2 text-sm font-semibold text-[#04201c] transition hover:bg-teal-300"
          >
            Start Evaluation
          </Link>
        </div>
        <button
          type="button"
          className="text-slate-300 md:hidden"
          aria-label="Menu"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </div>
      <div className={cn("border-t border-white/10 md:hidden", open ? "block" : "hidden")}>
        <div className="flex flex-col gap-2 px-4 py-4">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="py-2 text-sm text-slate-300"
              onClick={() => setOpen(false)}
            >
              {l.label}
            </Link>
          ))}
          <Link href="/login" className="py-2 text-sm text-slate-300" onClick={() => setOpen(false)}>
            Sign In
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-teal-400 px-4 py-2 text-center text-sm font-semibold text-[#04201c]"
            onClick={() => setOpen(false)}
          >
            Start Evaluation
          </Link>
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/10 bg-[#05080d] text-slate-400">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-4">
        <div className="md:col-span-1">
          <div className="mb-3 flex items-center gap-2 text-white">
            <Activity className="h-5 w-5 text-teal-300" />
            <span className="font-[family-name:var(--font-display)] text-sm font-semibold">
              Verspect
            </span>
          </div>
          <p className="text-sm leading-relaxed">
            Dependency intelligence for engineering teams who refuse to guess upgrades.
          </p>
        </div>
        {[
          {
            title: "Product",
            items: [
              { href: "/#scan-demo", label: "Scan demo" },
              { href: "/#simulator", label: "Upgrade Simulator" },
              { href: "/#migration", label: "AI Migration" },
              { href: "/pricing", label: "Pricing" },
              { href: "/roadmap", label: "Roadmap" },
              { href: "/changelog", label: "Changelog" },
              { href: "/docs", label: "Documentation" },
            ],
          },
          {
            title: "Company",
            items: [
              { href: "/blog", label: "Blog" },
              { href: "/contact", label: "Contact" },
              { href: "/feedback", label: "Feedback" },
              { href: "/legal/privacy", label: "Privacy" },
              { href: "/legal/terms", label: "Terms" },
            ],
          },
          {
            title: "Connect",
            items: [
              { href: "https://github.com", label: "GitHub" },
              { href: "https://linkedin.com", label: "LinkedIn" },
              { href: "https://twitter.com", label: "Twitter" },
              { href: "/legal/cookies", label: "Cookies" },
            ],
          },
        ].map((col) => (
          <div key={col.title}>
            <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {col.title}
            </div>
            <ul className="space-y-2 text-sm">
              {col.items.map((i) => (
                <li key={i.href}>
                  <Link href={i.href} className="hover:text-white">
                    {i.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-white/5 py-6 text-center text-xs text-slate-600">
        © {new Date().getFullYear()} Verspect. Built for teams who ship carefully.
      </div>
    </footer>
  );
}
