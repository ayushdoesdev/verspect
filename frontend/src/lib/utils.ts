import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(n);
}

export function formatScore(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toFixed(0);
}

export function severityColor(severity: string): string {
  switch (severity?.toLowerCase()) {
    case "critical":
      return "text-destructive";
    case "high":
      return "text-orange-400";
    case "medium":
      return "text-warning";
    case "low":
      return "text-chart-2";
    default:
      return "text-muted-foreground";
  }
}

export function statusBadge(status: string): string {
  switch (status) {
    case "vulnerable":
      return "bg-destructive/15 text-destructive border-destructive/30";
    case "outdated":
      return "bg-warning/15 text-warning border-warning/30";
    case "license_issue":
      return "bg-orange-500/15 text-orange-300 border-orange-500/30";
    case "up_to_date":
      return "bg-success/15 text-success border-success/30";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}
