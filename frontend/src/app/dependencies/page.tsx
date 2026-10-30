"use client";

import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useNavRouter } from "@/lib/nav-router";
import { formatScore, statusBadge } from "@/lib/utils";
import { AppShell, EmptyState, PageHeader } from "@/components/layout/app-shell";
import {
  DependenciesSkeleton,
  ErrorState,
  ListSkeleton,
  LoadingCopy,
  RefetchBar,
} from "@/components/loading";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NavLink } from "@/components/navigation/nav-link";
import { Boxes } from "lucide-react";

export default function DependenciesPage() {
  const router = useNavRouter();
  const auth = useRequireAuth();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [q, filter]);

  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const params = new URLSearchParams({
    page: String(page),
    page_size: "50",
    sort_by: "risk_score",
    sort_order: "desc",
  });
  if (q) params.set("search", q);
  if (filter === "outdated") params.set("is_outdated", "true");
  if (filter === "vulnerable") params.set("has_vulnerabilities", "true");

  const deps = useQuery({
    queryKey: ["dependencies", q, filter, page],
    queryFn: () => api.dependencies(`?${params.toString()}`),
    enabled: auth.isAuthenticated,
    placeholderData: keepPreviousData,
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <DependenciesSkeleton />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader
        title="Dependencies"
        description="All packages across watched repositories."
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <Input
          placeholder="Search packages…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="sm:max-w-sm"
        />
        <div className="flex gap-2">
          {["", "outdated", "vulnerable"].map((f) => (
            <button
              key={f || "all"}
              onClick={() => setFilter(f)}
              className={`rounded-md border px-3 py-2 text-xs ${
                filter === f
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {f || "all"}
            </button>
          ))}
        </div>
      </div>

      {deps.isLoading && !deps.data ? (
        <div className="space-y-3">
          <LoadingCopy>Loading dependency analysis…</LoadingCopy>
          <ListSkeleton rows={8} />
        </div>
      ) : deps.isError && !deps.data ? (
        <ErrorState
          title="Unable to load dependencies"
          description={(deps.error as Error)?.message || "Try again in a moment."}
          onRetry={() => deps.refetch()}
        />
      ) : (
        <div className="grid gap-2">
          <RefetchBar
            active={deps.isFetching && !deps.isLoading}
            label="Updating dependency analysis…"
          />
          {!(deps.data?.items || []).length ? (
            <EmptyState
              title="No dependencies yet"
              description="Import a repository and run a scan to discover packages."
              icon={<Boxes className="h-6 w-6" />}
              action={
                <Button onClick={() => router.push("/repositories")}>Import repositories</Button>
              }
            />
          ) : (
            (deps.data?.items || []).map((d) => (
              <NavLink key={d.id} href={`/dependencies/${d.id}`} interactive="card">
                <Card className="transition-colors hover:border-primary/40">
                  <CardContent className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{d.package_name}</span>
                        <Badge className={statusBadge(d.status)}>
                          {d.status.replaceAll("_", " ")}
                        </Badge>
                        {d.license_spdx ? (
                          <Badge className="border-border text-muted-foreground">
                            {d.license_spdx}
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                        {d.summary || d.ai_explanation || "No summary"}
                      </p>
                    </div>
                    <div className="flex gap-4 text-xs tabular-nums text-muted-foreground">
                      <span className="font-mono">
                        {d.current_version || "unpinned"} → {d.latest_version || "?"}
                      </span>
                      <span>Health {formatScore(d.health_score)}</span>
                      <span>Risk {formatScore(d.risk_score)}</span>
                      <span>{d.usage_count} uses</span>
                    </div>
                  </CardContent>
                </Card>
              </NavLink>
            ))
          )}
          {deps.data && deps.data.pages > 1 ? (
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Page {deps.data.page} of {deps.data.pages} ({deps.data.total} packages)
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!deps.data.has_prev}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!deps.data.has_next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </AppShell>
  );
}
