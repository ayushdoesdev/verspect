"use client";

import React from "react";
import { cn } from "@/lib/utils";

type Variant = "app" | "marketing";

/** Subtle Private Beta badge — navbar / landing / dashboard. */
export function PrivateBetaBadge({
  className,
  variant = "app",
}: {
  className?: string;
  variant?: Variant;
}) {
  return (
    <span
      data-testid="private-beta-badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        variant === "marketing"
          ? "border-teal-400/30 bg-teal-400/10 text-teal-200"
          : "border-primary/25 bg-primary/10 text-primary",
        className,
      )}
    >
      <span aria-hidden>🚧</span>
      Private Beta
    </span>
  );
}
