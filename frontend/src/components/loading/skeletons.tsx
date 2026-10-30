"use client";

import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { LoadingCopy } from "./states";

export function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={cn("skeleton-shimmer rounded-md bg-secondary/80", className)} style={style} />
  );
}

/** Alias for design-system naming. */
export function CardSkeleton({ className }: { className?: string }) {
  return <SkeletonCard className={className} />;
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-xl border border-border/60 p-4", className)}>
      <Skeleton className="mb-3 h-4 w-1/3" />
      <Skeleton className="mb-2 h-3 w-full" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  );
}

export function PageSkeleton({
  titleWidth = "w-48",
  children,
  copy,
}: {
  titleWidth?: string;
  children?: ReactNode;
  copy?: string;
}) {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className={cn("mb-2 h-8", titleWidth)} />
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      {copy ? <LoadingCopy>{copy}</LoadingCopy> : null}
      {children}
    </div>
  );
}

export function TableSkeleton({
  rows = 6,
  cols = 4,
  className,
}: {
  rows?: number;
  cols?: number;
  className?: string;
}) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-border/60", className)}>
      <div className="grid gap-3 border-b border-border/50 bg-secondary/20 px-4 py-3 sm:grid-cols-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-20" />
        ))}
      </div>
      <div className="divide-y divide-border/40">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="grid gap-3 px-4 py-3 sm:grid-cols-4">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className="h-4 w-full" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ListSkeleton({
  rows = 5,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2 animate-fade-up", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 rounded-xl border border-border/60 px-4 py-3"
        >
          <Skeleton className="h-9 w-9 shrink-0 rounded-lg" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-48 max-w-full" />
            <Skeleton className="h-3 w-72 max-w-full" />
          </div>
          <Skeleton className="hidden h-6 w-16 sm:block" />
        </div>
      ))}
    </div>
  );
}

export function CodeBlockSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "space-y-2 rounded-xl border border-border/60 bg-secondary/20 p-4 font-mono animate-fade-up",
        className,
      )}
    >
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-3"
          style={{ width: `${55 + ((i * 13) % 40)}%` } as CSSProperties}
        />
      ))}
    </div>
  );
}

export function RepositorySkeleton({ className }: { className?: string }) {
  return <RepositoriesSkeleton className={className} />;
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <LoadingCopy>Loading dashboard…</LoadingCopy>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border/60 p-4">
            <Skeleton className="mb-3 h-3 w-16" />
            <Skeleton className="h-7 w-12" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </div>
  );
}

export function RepositoriesSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3 animate-fade-up", className)}>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border/60 p-5">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-5 w-56 max-w-full" />
              <Skeleton className="h-3 w-80 max-w-full" />
            </div>
            <div className="hidden gap-4 sm:flex">
              <Skeleton className="h-8 w-10" />
              <Skeleton className="h-8 w-10" />
              <Skeleton className="h-8 w-10" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function RepositoryPageSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-64 max-w-full" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <LoadingCopy>Loading repository…</LoadingCopy>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border/60 p-4">
            <Skeleton className="mb-2 h-3 w-20" />
            <Skeleton className="h-6 w-12" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <SkeletonCard className="min-h-40" />
        <SkeletonCard className="min-h-40" />
      </div>
      <TableSkeleton rows={6} cols={4} />
    </div>
  );
}

export function DependenciesSkeleton() {
  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-44" />
        <Skeleton className="h-4 w-64" />
      </div>
      <LoadingCopy>Loading dependency analysis…</LoadingCopy>
      <div className="flex flex-wrap gap-2">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-9 w-28" />
      </div>
      <ListSkeleton rows={8} />
    </div>
  );
}

export function DependencyPageSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-52" />
        <Skeleton className="h-4 w-64" />
      </div>
      <LoadingCopy>Loading dependency analysis…</LoadingCopy>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-20 rounded-full" />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border/60 p-4">
            <Skeleton className="mb-2 h-3 w-16" />
            <Skeleton className="h-6 w-20" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <KnowledgeCardSkeleton title="Upgrade Advisor" />
        <KnowledgeCardSkeleton title="Migration Plan" />
        <KnowledgeCardSkeleton title="Security" />
      </div>
      <SkeletonCard className="min-h-56" />
      <CodeBlockSkeleton />
    </div>
  );
}

export function SecuritySkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <LoadingCopy>Loading security findings…</LoadingCopy>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border/60 p-4">
            <Skeleton className="mb-3 h-3 w-20" />
            <Skeleton className="h-8 w-14" />
          </div>
        ))}
      </div>
      <ListSkeleton rows={6} />
    </div>
  );
}

export function PackageGridSkeleton({
  copy = "Loading packages…",
}: {
  copy?: string;
}) {
  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-56" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <LoadingCopy>{copy}</LoadingCopy>
      <div className="grid gap-3 md:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border/70 bg-card/40 px-4 py-3">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4 rounded" />
              <Skeleton className="h-4 w-40" />
            </div>
            <Skeleton className="mt-2 h-3 w-36 font-mono" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function UpgradeSimulatorSkeleton() {
  return <PackageGridSkeleton copy="Preparing upgrade analysis…" />;
}

export function MigrationAssistantSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <LoadingCopy>Loading AI Migration Assistant…</LoadingCopy>
      <SkeletonCard className="min-h-40" />
      <PackageGridSkeleton copy="Loading packages…" />
    </div>
  );
}

export function SearchSkeleton() {
  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-32" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Skeleton className="h-10 w-full max-w-xl" />
      <LoadingCopy>Searching…</LoadingCopy>
      <ListSkeleton rows={5} />
    </div>
  );
}

export function SettingsSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-36" />
        <Skeleton className="h-4 w-64" />
      </div>
      <LoadingCopy>Loading settings…</LoadingCopy>
      <div className="space-y-4 rounded-xl border border-border/60 p-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between gap-4 border-b border-border/40 py-3 last:border-0">
            <div className="space-y-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-64 max-w-full" />
            </div>
            <Skeleton className="h-6 w-11 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function AiSettingsSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <LoadingCopy>Loading AI settings…</LoadingCopy>
      <div className="grid gap-4 lg:grid-cols-2">
        <SkeletonCard className="min-h-36" />
        <SkeletonCard className="min-h-36" />
      </div>
      <SkeletonCard className="min-h-48" />
    </div>
  );
}

export function UsageSkeleton() {
  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-28" />
        <Skeleton className="h-4 w-64" />
      </div>
      <LoadingCopy>Loading usage…</LoadingCopy>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border/60 p-4">
            <Skeleton className="mb-3 h-3 w-28" />
            <Skeleton className="h-8 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function JobsSkeleton() {
  return (
    <div className="space-y-3 animate-fade-up">
      <LoadingCopy>Loading background jobs…</LoadingCopy>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="space-y-2">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-3 w-56" />
            </div>
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
          <Skeleton className="mt-3 h-2 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function KnowledgeCardSkeleton({ title }: { title?: string }) {
  return (
    <div className="rounded-xl border border-border/60 p-4">
      {title ? (
        <div className="mb-3 text-xs font-medium text-muted-foreground">{title}</div>
      ) : (
        <Skeleton className="mb-3 h-3 w-24" />
      )}
      <Skeleton className="mb-2 h-3 w-full" />
      <Skeleton className="mb-2 h-3 w-5/6" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="rounded-xl border border-border/60 p-4">
      <Skeleton className="mb-4 h-4 w-32" />
      <div className="flex h-40 items-end gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton
            key={i}
            className="w-full"
            style={{ height: `${30 + ((i * 17) % 60)}%` } as CSSProperties}
          />
        ))}
      </div>
    </div>
  );
}

export function PricingSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-border/60 p-6">
          <Skeleton className="mb-2 h-5 w-24" />
          <Skeleton className="mb-6 h-8 w-20" />
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, j) => (
              <Skeleton key={j} className="h-3 w-full" />
            ))}
          </div>
          <Skeleton className="mt-6 h-10 w-full" />
        </div>
      ))}
    </div>
  );
}

export function BillingSkeleton() {
  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <LoadingCopy>Loading billing information…</LoadingCopy>
      <div className="grid gap-4 lg:grid-cols-2">
        <SkeletonCard className="min-h-40" />
        <SkeletonCard className="min-h-40" />
      </div>
      <SkeletonCard />
    </div>
  );
}

export function OrganizationsSkeleton() {
  return (
    <div className="space-y-4 animate-fade-up">
      <div>
        <Skeleton className="mb-2 h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <LoadingCopy>Loading organization…</LoadingCopy>
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-border/60 p-3">
            <Skeleton className="h-9 w-9 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function AiSectionSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-3 animate-fade-up">
      <KnowledgeCardSkeleton title="Upgrade Advisor" />
      <KnowledgeCardSkeleton title="Migration Plan" />
      <KnowledgeCardSkeleton title="Security" />
    </div>
  );
}

/** Auth / session bootstrap — keep shell chrome, fill content area. */
export function SessionSkeleton({
  variant = "dashboard",
}: {
  variant?:
    | "dashboard"
    | "repositories"
    | "repository"
    | "dependencies"
    | "dependency"
    | "security"
    | "simulator"
    | "migration"
    | "search"
    | "team"
    | "billing"
    | "usage"
    | "settings"
    | "ai-settings"
    | "generic";
}) {
  switch (variant) {
    case "dashboard":
      return <DashboardSkeleton />;
    case "repositories":
      return (
        <PageSkeleton copy="Loading repositories…">
          <RepositoriesSkeleton />
        </PageSkeleton>
      );
    case "repository":
      return <RepositoryPageSkeleton />;
    case "dependencies":
      return <DependenciesSkeleton />;
    case "dependency":
      return <DependencyPageSkeleton />;
    case "security":
      return <SecuritySkeleton />;
    case "simulator":
      return <UpgradeSimulatorSkeleton />;
    case "migration":
      return <MigrationAssistantSkeleton />;
    case "search":
      return <SearchSkeleton />;
    case "team":
      return <OrganizationsSkeleton />;
    case "billing":
      return <BillingSkeleton />;
    case "usage":
      return <UsageSkeleton />;
    case "settings":
      return <SettingsSkeleton />;
    case "ai-settings":
      return <AiSettingsSkeleton />;
    default:
      return (
        <PageSkeleton copy="Loading…">
          <ListSkeleton />
        </PageSkeleton>
      );
  }
}
