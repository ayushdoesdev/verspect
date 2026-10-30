"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Activity, ChevronDown, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const primaryLinks = [
  { href: "/#scan-demo", label: "Product" },
  { href: "/#simulator", label: "Simulator" },
  { href: "/#migration", label: "Migration" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
];

const moreLinks = [
  { href: "/roadmap", label: "Roadmap" },
  { href: "/changelog", label: "Changelog" },
  { href: "/feedback", label: "Feedback" },
  { href: "/contact", label: "Contact" },
];

const mobileLinks = [...primaryLinks, ...moreLinks];

const navItemClass =
  "inline-flex min-h-10 items-center justify-center whitespace-nowrap rounded-md px-2.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300";

export function MarketingNav() {
  const [open, setOpen] = useState(false);
  const [hash, setHash] = useState("");
  const pathname = usePathname();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const firstMobileLinkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash);
    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, [pathname]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;

    firstMobileLinkRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menuButtonRef.current?.focus();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const isActive = (href: string) => {
    if (href.startsWith("/#")) {
      if (pathname !== "/") return false;
      const targetHash = href.slice(1);
      return (hash || "#scan-demo") === targetHash;
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const linkClass = (href: string) =>
    cn(
      navItemClass,
      isActive(href)
        ? "bg-white/[0.06] text-teal-200"
        : "text-slate-400 hover:bg-white/[0.04] hover:text-white",
    );
  const moreActive = moreLinks.some((link) => isActive(link.href));

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#070b12]/80 backdrop-blur-xl">
      <div className="mx-auto grid h-20 max-w-[1440px] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 sm:px-6 xl:grid-cols-[minmax(250px,1fr)_auto_minmax(250px,1fr)] xl:gap-6 xl:px-10">
        <Link
          href="/"
          aria-label="Verspect home"
          className="flex min-w-0 items-center gap-2.5 whitespace-nowrap justify-self-start focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-300"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-400/15 text-teal-300 ring-1 ring-teal-400/30">
            <Activity className="h-5 w-5" />
          </span>
          <span className="font-[family-name:var(--font-display)] text-base font-semibold tracking-tight text-white">
            Verspect
          </span>
          <PrivateBetaBadge variant="marketing" className="shrink-0" />
        </Link>

        <nav aria-label="Primary navigation" className="hidden items-center gap-1 xl:flex">
          {primaryLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={linkClass(link.href)}
              aria-current={isActive(link.href) ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                navItemClass,
                moreActive
                  ? "bg-white/[0.06] text-teal-200"
                  : "text-slate-400 hover:bg-white/[0.04] hover:text-white",
              )}
              aria-label="More pages"
            >
              More <ChevronDown aria-hidden="true" className="ml-1 h-3.5 w-3.5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="center"
              sideOffset={10}
              className="min-w-48 border-white/10 bg-[#0b111b] p-1.5 text-slate-200 shadow-2xl"
            >
              {moreLinks.map((link) => (
                <DropdownMenuItem key={link.href} asChild>
                  <Link
                    href={link.href}
                    aria-current={isActive(link.href) ? "page" : undefined}
                    className={cn(
                      "min-h-10 px-3 text-sm focus:bg-white/[0.08] focus:text-white",
                      isActive(link.href) && "text-teal-200",
                    )}
                  >
                    {link.label}
                  </Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>

        <div className="hidden items-center justify-self-end gap-5 xl:flex">
          <Link
            href="/login"
            className="whitespace-nowrap rounded-md px-1 py-2 text-sm font-medium text-slate-300 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-300"
          >
            Sign In
          </Link>
          <Link
            href="/signup"
            className="inline-flex min-h-10 shrink-0 items-center justify-center whitespace-nowrap rounded-full bg-teal-400 px-5 py-2.5 text-sm font-semibold leading-none text-[#04201c] transition-colors hover:bg-teal-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-200"
          >
            Start Evaluation
          </Link>
        </div>
        <button
          type="button"
          ref={menuButtonRef}
          className="inline-flex h-11 w-11 items-center justify-center justify-self-end rounded-lg border border-white/10 text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300 xl:hidden"
          aria-label={open ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={open}
          aria-controls="mobile-navigation-panel"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <X aria-hidden="true" className="h-5 w-5" />
          ) : (
            <Menu aria-hidden="true" className="h-5 w-5" />
          )}
        </button>
      </div>

      <div
        id="mobile-navigation-panel"
        className={cn(
          "border-t border-white/10 bg-[#070b12] xl:hidden",
          open ? "block" : "hidden",
        )}
      >
        <nav
          aria-label="Mobile navigation"
          className="mx-auto max-h-[calc(100dvh-5rem)] max-w-[1440px] overflow-y-auto px-4 py-3 sm:px-6"
        >
          <div className="flex flex-col gap-1">
            {mobileLinks.map((link, index) => (
              <Link
                key={link.href}
                ref={index === 0 ? firstMobileLinkRef : undefined}
                href={link.href}
                className={cn(
                  "flex min-h-11 items-center rounded-lg px-3 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-300",
                  isActive(link.href)
                    ? "bg-white/[0.06] text-teal-200"
                    : "text-slate-300 hover:bg-white/[0.04] hover:text-white",
                )}
                aria-current={isActive(link.href) ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
          </div>
          <div className="mt-3 flex flex-col gap-2 border-t border-white/10 pt-3">
            <Link
              href="/login"
              className="flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-slate-300 transition-colors hover:bg-white/[0.04] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-300"
              onClick={() => setOpen(false)}
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="inline-flex min-h-11 items-center justify-center rounded-full bg-teal-400 px-5 py-2.5 text-sm font-semibold leading-none text-[#04201c] transition-colors hover:bg-teal-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-200"
              onClick={() => setOpen(false)}
            >
              Start Evaluation
            </Link>
          </div>
        </nav>
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
