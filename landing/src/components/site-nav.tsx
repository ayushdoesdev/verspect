"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const links = [
  ["#features", "Features"],
  ["#ecosystems", "Ecosystems"],
  ["#self-hosting", "Self-hosting"],
  ["#documentation", "Documentation"],
  ["#faq", "FAQ"],
] as const;

export function SiteNav() {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstLink = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;
    firstLink.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <header className="site-header">
      <div className="nav-inner">
        <Link href="#top" className="brand" aria-label="Verspect home">
          <span className="brand-mark" aria-hidden="true"><BrandMark /></span>
          <span>Verspect</span>
        </Link>
        <nav className="desktop-nav" aria-label="Main navigation">
          {links.map(([href, label]) => <Link key={href} href={href}>{label}</Link>)}
        </nav>
        <a className="nav-github" href="https://github.com/ayushdoesdev/verspect" target="_blank" rel="noreferrer noopener">
          GitHub <span aria-hidden="true">↗</span>
        </a>
        <button
          ref={trigger}
          type="button"
          className="menu-toggle"
          aria-label={open ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={open}
          aria-controls="mobile-navigation"
          onClick={() => setOpen((value) => !value)}
        >
          <span /><span />
        </button>
      </div>
      <nav id="mobile-navigation" aria-label="Mobile navigation" className={`mobile-nav${open ? " is-open" : ""}`} hidden={!open}>
        {links.map(([href, label], index) => (
          <Link key={href} href={href} ref={index === 0 ? firstLink : undefined} onClick={() => setOpen(false)}>{label}</Link>
        ))}
        <a href="https://github.com/ayushdoesdev/verspect" target="_blank" rel="noreferrer noopener" onClick={() => setOpen(false)}>GitHub ↗</a>
      </nav>
    </header>
  );
}

export function BrandMark() {
  return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M3 16h7l4 12 6-24 4 12h5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
