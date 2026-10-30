"use client";

import Link from "next/link";
import { useLinkStatus } from "next/link";
import { useRouter } from "next/navigation";
import {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { startNavigation } from "@/components/navigation/navigation-progress";

type NavLinkProps = Omit<ComponentProps<typeof Link>, "prefetch"> & {
  /** Visual density for list rows / cards / nav items. */
  interactive?: "row" | "card" | "nav" | "plain";
  prefetchOnVisible?: boolean;
  children: ReactNode;
};

/** Bridges useLinkStatus (must be under Link) up to the anchor's pending class. */
function PendingBridge({ onPending }: { onPending: (pending: boolean) => void }) {
  const { pending } = useLinkStatus();
  useEffect(() => {
    onPending(pending);
  }, [pending, onPending]);
  return null;
}

export const NavLink = forwardRef<HTMLAnchorElement, NavLinkProps>(function NavLink(
  {
    href,
    className,
    children,
    interactive = "plain",
    prefetchOnVisible = true,
    onClick,
    onMouseEnter,
    onPointerDown,
    ...rest
  },
  ref,
) {
  const router = useRouter();
  const rootRef = useRef<HTMLAnchorElement | null>(null);
  const lockRef = useRef(false);
  const [pending, setPending] = useState(false);
  const [pressed, setPressed] = useState(false);
  const hrefStr = typeof href === "string" ? href : href.pathname || "";

  const setRefs = useCallback(
    (node: HTMLAnchorElement | null) => {
      rootRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    },
    [ref],
  );

  const handlePending = useCallback((next: boolean) => {
    setPending(next);
    if (!next) lockRef.current = false;
  }, []);

  useEffect(() => {
    if (!prefetchOnVisible || !hrefStr.startsWith("/")) return;
    const el = rootRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          router.prefetch(hrefStr);
          io.disconnect();
        }
      },
      { rootMargin: "240px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hrefStr, prefetchOnVisible, router]);

  return (
    <Link
      ref={setRefs}
      href={href}
      prefetch
      data-pending={pending ? "true" : "false"}
      data-pressed={pressed ? "true" : "false"}
      aria-busy={pending || undefined}
      aria-disabled={pending || undefined}
      className={cn(
        "nav-interactive min-w-0",
        interactive === "row" && "nav-interactive-row",
        interactive === "card" && "nav-interactive-card",
        interactive === "nav" && "nav-interactive-nav",
        pending && "nav-interactive-pending",
        pressed && !pending && "nav-interactive-pressed",
        className,
      )}
      onMouseEnter={(e) => {
        if (hrefStr.startsWith("/")) router.prefetch(hrefStr);
        onMouseEnter?.(e);
      }}
      onPointerDown={(e) => {
        if (e.button === 0) setPressed(true);
        onPointerDown?.(e);
      }}
      onPointerUp={() => setPressed(false)}
      onPointerLeave={() => setPressed(false)}
      onPointerCancel={() => setPressed(false)}
      onClick={(e) => {
        if (lockRef.current || pending) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        if (!e.defaultPrevented && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
          lockRef.current = true;
          startNavigation(hrefStr);
          setPending(true);
          setPressed(false);
        }
        onClick?.(e);
      }}
      {...rest}
    >
      <PendingBridge onPending={handlePending} />
      {children}
    </Link>
  );
});
