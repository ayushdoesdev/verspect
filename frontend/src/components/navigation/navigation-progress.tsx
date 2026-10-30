"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

type NavState = "idle" | "loading" | "finishing";

type NavigationController = {
  start: (href?: string) => void;
  done: () => void;
};

let controller: NavigationController | null = null;

/** Start the global top bar (for programmatic router.push / replace). */
export function startNavigation(href?: string) {
  controller?.start(href);
}

export function finishNavigation() {
  controller?.done();
}

function NavigationProgressInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [state, setState] = useState<NavState>("idle");
  const [progress, setProgress] = useState(0);
  const startedAt = useRef(0);
  const tickRef = useRef<number | null>(null);
  const finishTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingHref = useRef<string | null>(null);
  const routeKey = `${pathname}?${searchParams?.toString() || ""}`;

  const clearTick = () => {
    if (tickRef.current != null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  };

  const done = useCallback(() => {
    clearTick();
    if (finishTimer.current) clearTimeout(finishTimer.current);
    const elapsed = Date.now() - startedAt.current;
    const wait = Math.max(0, 180 - elapsed);
    setState("finishing");
    setProgress(100);
    finishTimer.current = setTimeout(() => {
      setState("idle");
      setProgress(0);
      pendingHref.current = null;
    }, wait + 220);
  }, []);

  const start = useCallback(
    (href?: string) => {
      if (typeof window === "undefined") return;
      if (href) {
        try {
          const url = new URL(href, window.location.origin);
          const nextKey = `${url.pathname}?${url.searchParams.toString()}`;
          const currentKey = `${window.location.pathname}?${window.location.search.replace(/^\?/, "")}`;
          if (nextKey === currentKey || url.pathname === window.location.pathname && url.search === window.location.search) {
            return;
          }
          pendingHref.current = url.pathname + url.search;
        } catch {
          pendingHref.current = href;
        }
      }
      if (finishTimer.current) clearTimeout(finishTimer.current);
      clearTick();
      startedAt.current = Date.now();
      setState("loading");
      setProgress(12);
      tickRef.current = window.setInterval(() => {
        setProgress((p) => {
          if (p >= 88) return p;
          const step = p < 40 ? 8 : p < 70 ? 4 : 1.5;
          return Math.min(88, p + step);
        });
      }, 180);
    },
    [],
  );

  useEffect(() => {
    controller = { start, done };
    return () => {
      if (controller?.start === start) controller = null;
    };
  }, [start, done]);

  // Capture link clicks immediately — before Next.js navigation work.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented) return;
      if (event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target as Element | null;
      const anchor = target?.closest?.("a");
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return;
      if (anchor.hasAttribute("download")) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
        return;
      }
      if (/^https?:\/\//i.test(href) && !href.startsWith(window.location.origin)) {
        return;
      }
      start(href);
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [start]);

  // Route settled → complete the bar.
  useEffect(() => {
    if (state === "loading" || pendingHref.current) {
      done();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on route identity change
  }, [routeKey]);

  useEffect(
    () => () => {
      clearTick();
      if (finishTimer.current) clearTimeout(finishTimer.current);
    },
    [],
  );

  const visible = state !== "idle";

  return (
    <div
      className={cn(
        "pointer-events-none fixed inset-x-0 top-0 z-[200] h-[2px]",
        visible ? "opacity-100" : "opacity-0",
      )}
      aria-hidden
    >
      <div
        className={cn(
          "h-full origin-left bg-primary shadow-[0_0_12px_color-mix(in_oklab,var(--primary)_70%,transparent)] transition-[width,opacity] duration-200 ease-out",
          state === "finishing" && "opacity-0",
        )}
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}

export function NavigationProgress() {
  return (
    <Suspense fallback={null}>
      <NavigationProgressInner />
    </Suspense>
  );
}
