"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Activity, ChevronDown, Menu, X } from "lucide-react";

const repository = "https://github.com/ayushdoesdev/verspect";
const documentation = `${repository}/tree/main/docs`;
const primaryLinks = [
  { href: "#scan-demo", label: "Product" },
  { href: "#simulator", label: "Simulator" },
  { href: "#migration", label: "Migration" },
  { href: "#faq", label: "FAQ" },
] as const;
const moreLinks = [
  { href: `${repository}/releases`, label: "Releases" },
  { href: `${repository}/issues`, label: "Issues & feedback" },
  { href: `${repository}/blob/main/CONTRIBUTING.md`, label: "Contributing" },
] as const;

export function MarketingNav() {
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const firstMobileLinkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;
    firstMobileLinkRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menuButtonRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (!moreOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMoreOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [moreOpen]);

  const closeMenus = () => {
    setOpen(false);
    setMoreOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#070b12]/80 backdrop-blur-xl">
      <div className="mx-auto grid h-20 max-w-[1440px] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 sm:px-6 xl:grid-cols-[minmax(250px,1fr)_auto_minmax(250px,1fr)] xl:gap-6 xl:px-10">
        <Link href="/" aria-label="Verspect home" className="flex min-w-0 items-center gap-2.5 whitespace-nowrap justify-self-start focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-300">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-400/15 text-teal-300 ring-1 ring-teal-400/30"><Activity className="h-5 w-5" /></span>
          <span className="font-[family-name:var(--font-display)] text-base font-semibold tracking-tight text-white">Verspect</span>
        </Link>

        <nav aria-label="Primary navigation" className="hidden items-center gap-1 xl:flex">
          {primaryLinks.map((link) => <Link key={link.href} href={link.href} className="inline-flex min-h-10 items-center justify-center whitespace-nowrap rounded-md px-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300">{link.label}</Link>)}
          <a href={documentation} target="_blank" rel="noreferrer noopener" className="inline-flex min-h-10 items-center justify-center whitespace-nowrap rounded-md px-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300">Docs</a>
          <div className="relative">
            <button type="button" onClick={() => setMoreOpen((value) => !value)} aria-expanded={moreOpen} aria-haspopup="true" className="inline-flex min-h-10 items-center justify-center whitespace-nowrap rounded-md px-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300">
              More <ChevronDown aria-hidden="true" className={`ml-1 h-3.5 w-3.5 transition-transform ${moreOpen ? "rotate-180" : ""}`} />
            </button>
            {moreOpen && <div className="absolute right-0 top-full z-50 mt-2 min-w-48 rounded-xl border border-white/10 bg-[#0b111b] p-1.5 text-slate-200 shadow-2xl">
              {moreLinks.map((link) => <a key={link.href} href={link.href} target="_blank" rel="noreferrer noopener" onClick={() => setMoreOpen(false)} className="flex min-h-10 items-center rounded-lg px-3 text-sm text-slate-300 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-300">{link.label}</a>)}
            </div>}
          </div>
        </nav>

        <div className="hidden items-center justify-self-end gap-5 xl:flex">
          <a href={repository} target="_blank" rel="noreferrer noopener" className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-full bg-teal-400 px-5 py-2.5 text-sm font-semibold leading-none text-[#04201c] transition-colors hover:bg-teal-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-200">GitHub <span aria-hidden="true">↗</span></a>
        </div>

        <button type="button" ref={menuButtonRef} className="inline-flex h-11 w-11 items-center justify-center justify-self-end rounded-lg border border-white/10 text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300 xl:hidden" aria-label={open ? "Close navigation menu" : "Open navigation menu"} aria-expanded={open} aria-controls="mobile-navigation-panel" onClick={() => setOpen((value) => !value)}>
          {open ? <X aria-hidden="true" className="h-5 w-5" /> : <Menu aria-hidden="true" className="h-5 w-5" />}
        </button>
      </div>

      <div id="mobile-navigation-panel" className={`border-t border-white/10 bg-[#070b12] xl:hidden ${open ? "block" : "hidden"}`}>
        <nav aria-label="Mobile navigation" className="mx-auto max-h-[calc(100dvh-5rem)] max-w-[1440px] overflow-y-auto px-4 py-3 sm:px-6">
          <div className="flex flex-col gap-1">
            {primaryLinks.map((link, index) => <Link key={link.href} ref={index === 0 ? firstMobileLinkRef : undefined} href={link.href} className="flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-slate-300 transition-colors hover:bg-white/[0.04] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-300" onClick={closeMenus}>{link.label}</Link>)}
            <a href={documentation} target="_blank" rel="noreferrer noopener" className="flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-slate-300 transition-colors hover:bg-white/[0.04] hover:text-white" onClick={closeMenus}>Documentation ↗</a>
          </div>
          <div className="mt-3 border-t border-white/10 pt-3">
            <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">More</div>
            <div className="flex flex-col gap-1">{moreLinks.map((link) => <a key={link.href} href={link.href} target="_blank" rel="noreferrer noopener" className="flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-slate-300 transition-colors hover:bg-white/[0.04] hover:text-white" onClick={closeMenus}>{link.label} ↗</a>)}</div>
            <a href={repository} target="_blank" rel="noreferrer noopener" className="mt-3 inline-flex min-h-11 w-full items-center justify-center rounded-full bg-teal-400 px-5 py-2.5 text-sm font-semibold leading-none text-[#04201c] transition-colors hover:bg-teal-300" onClick={closeMenus}>View on GitHub ↗</a>
          </div>
        </nav>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  const columns = [
    { title: "Product", links: [
      { href: "#scan-demo", label: "Repository scan" },
      { href: "#simulator", label: "Upgrade Simulator" },
      { href: "#migration", label: "Migration Assistant" },
      { href: "#graph", label: "Dependency graph" },
      { href: "#faq", label: "FAQ" },
    ]},
    { title: "Resources", links: [
      { href: documentation, label: "Documentation" },
      { href: `${repository}/releases`, label: "Releases" },
      { href: `${repository}/issues`, label: "Issues & feedback" },
      { href: `${repository}/blob/main/CONTRIBUTING.md`, label: "Contributing" },
    ]},
    { title: "Project", links: [
      { href: repository, label: "GitHub repository" },
      { href: `${repository}/blob/main/LICENSE`, label: "Apache-2.0 license" },
      { href: `${repository}/blob/main/THIRD_PARTY_NOTICES.md`, label: "Third-party notices" },
      { href: `${repository}/blob/main/SECURITY.md`, label: "Security policy" },
    ]},
  ];

  return (
    <footer className="border-t border-white/10 bg-[#05080d] text-slate-400">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-4">
        <div className="md:col-span-1">
          <div className="mb-3 flex items-center gap-2 text-white"><Activity className="h-5 w-5 text-teal-300" /><span className="font-[family-name:var(--font-display)] text-sm font-semibold">Verspect</span></div>
          <p className="text-sm leading-relaxed">Dependency intelligence for GitHub repositories. Self-host it, inspect the source, and understand your upgrades.</p>
          <p className="mt-3 text-[10px] text-slate-500">Open source · Apache-2.0 on main</p>
        </div>
        {columns.map((column) => <div key={column.title}>
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{column.title}</div>
          <ul className="space-y-2 text-sm">{column.links.map((link) => <li key={link.href}>
            {link.href.startsWith("#") ? <Link href={link.href} className="hover:text-white">{link.label}</Link> : <a href={link.href} target="_blank" rel="noreferrer noopener" className="hover:text-white">{link.label} ↗</a>}
          </li>)}</ul>
        </div>)}
      </div>
      <div className="border-t border-white/5 py-6 text-center text-xs text-slate-600">© {new Date().getFullYear()} Verspect contributors. Verspect name, logo, and official branding are reserved.</div>
    </footer>
  );
}
