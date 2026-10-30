"use client";

import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Friendly progress line under skeletons / near content. */
export function LoadingCopy({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "flex items-center gap-2 text-sm text-muted-foreground animate-fade-up",
        className,
      )}
    >
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
      <span>{children}</span>
    </p>
  );
}

/** Compact spinner for refresh / retry / widgets. */
export function InlineSpinner({
  className,
  label,
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground", className)}
      role="status"
      aria-live="polite"
    >
      <Loader2 className={cn("h-3.5 w-3.5 animate-spin text-primary", className)} />
      {label ? <span>{label}</span> : <span className="sr-only">Loading</span>}
    </span>
  );
}

/** Subtle refetch indicator when cached content is already shown. */
export function RefetchBar({
  active,
  label = "Updating…",
}: {
  active: boolean;
  label?: string;
}) {
  if (!active) return null;
  return (
    <div className="mb-3 flex items-center gap-2 rounded-lg border border-border/60 bg-secondary/30 px-3 py-1.5 text-xs text-muted-foreground animate-fade-up">
      <Loader2 className="h-3 w-3 animate-spin text-primary" />
      {label}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description = "We couldn’t load this data. Check your connection and try again.",
  onRetry,
  retryLabel = "Retry",
  className,
  action,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-destructive/25 bg-destructive/5 px-6 py-14 text-center animate-fade-up",
        className,
      )}
      role="alert"
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h3 className="text-lg font-medium tracking-tight">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {onRetry ? (
          <Button type="button" onClick={onRetry} size="sm">
            <RefreshCw className="h-3.5 w-3.5" />
            {retryLabel}
          </Button>
        ) : null}
        {action}
      </div>
    </div>
  );
}

export function EmptyStatePanel({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-gradient-to-b from-secondary/20 to-transparent px-6 py-16 text-center animate-fade-up",
        className,
      )}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        {icon || <Inbox className="h-6 w-6" />}
      </div>
      <h3 className="text-lg font-medium tracking-tight">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/**
 * Standard query rendering helper:
 * - Initial load → skeleton
 * - Error with no data → ErrorState
 * - Cached data + refetch → content + RefetchBar
 */
export function QueryBoundary({
  isLoading,
  isError,
  isFetching,
  hasData,
  onRetry,
  skeleton,
  errorTitle,
  errorDescription,
  refetchLabel,
  loadingCopy,
  children,
}: {
  isLoading: boolean;
  isError?: boolean;
  isFetching?: boolean;
  hasData: boolean;
  onRetry?: () => void;
  skeleton: ReactNode;
  errorTitle?: string;
  errorDescription?: string;
  refetchLabel?: string;
  loadingCopy?: string;
  children: ReactNode;
}) {
  if (isLoading && !hasData) {
    return (
      <div className="space-y-3">
        {loadingCopy ? <LoadingCopy>{loadingCopy}</LoadingCopy> : null}
        {skeleton}
      </div>
    );
  }

  if (isError && !hasData) {
    return (
      <ErrorState
        title={errorTitle}
        description={errorDescription}
        onRetry={onRetry}
      />
    );
  }

  return (
    <div>
      <RefetchBar active={Boolean(isFetching && hasData && !isLoading)} label={refetchLabel} />
      {children}
    </div>
  );
}
