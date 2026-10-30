"use client";

import { ErrorState } from "@/components/loading";
import { cn } from "@/lib/utils";

export function AdminTable({
  headers,
  rows,
  loading,
  error,
  onRetry,
  onRowClick,
}: {
  headers: string[];
  rows: React.ReactNode[][];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  onRowClick?: (index: number) => void;
}) {
  if (error) {
    return <ErrorState title="Failed to load" onRetry={onRetry} />;
  }
  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-secondary/40 text-xs text-muted-foreground">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={cn(
                "border-t border-border/60",
                onRowClick && "cursor-pointer hover:bg-accent/40",
              )}
              onClick={() => onRowClick?.(i)}
            >
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length ? (
            <tr>
              <td colSpan={headers.length} className="px-3 py-6 text-muted-foreground">
                No results
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

export function AdminStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}
