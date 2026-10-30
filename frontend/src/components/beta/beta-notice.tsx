"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { PRICING_COPY } from "@/lib/evaluation-copy";

const STORAGE_KEY = "verspect.beta-notice.dismissed";

/** Non-intrusive Private Beta notice for authenticated surfaces. */
export function BetaNotice({ className }: { className?: string }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "1") return;
    } catch {
      /* ignore */
    }
    setVisible(true);
  }, []);

  if (!visible) return null;

  return (
    <div
      data-testid="beta-notice"
      className={cn(
        "mb-4 flex items-start gap-3 rounded-xl border border-border/70 bg-secondary/30 px-3.5 py-2.5 text-xs text-muted-foreground sm:text-sm",
        className,
      )}
    >
      <p className="min-w-0 flex-1 leading-relaxed">{PRICING_COPY.notice}</p>
      <button
        type="button"
        aria-label="Dismiss beta notice"
        className="shrink-0 rounded-md p-1 text-muted-foreground transition hover:bg-accent hover:text-foreground"
        onClick={() => {
          try {
            localStorage.setItem(STORAGE_KEY, "1");
          } catch {
            /* ignore */
          }
          setVisible(false);
        }}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
