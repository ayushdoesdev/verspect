"use client";

import { useEffect, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  ErrorState,
  ListSkeleton,
  LoadingCopy,
  RefetchBar,
  SearchSkeleton,
} from "@/components/loading";
import { NavLink } from "@/components/navigation/nav-link";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SearchPage() {
  const auth = useRequireAuth();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const results = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => api.search(debounced),
    enabled: auth.isAuthenticated && debounced.length > 0,
    placeholderData: keepPreviousData,
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <SearchSkeleton />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader
        title="Search"
        description="Find dependencies, repositories, files, and functions."
      />
      <Input
        autoFocus
        placeholder="Search packages, files, symbols…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="mb-6 max-w-xl"
      />
      {!debounced ? (
        <p className="text-sm text-muted-foreground">Type to search across your workspace.</p>
      ) : results.isLoading && !results.data ? (
        <div className="space-y-3">
          <LoadingCopy>Searching…</LoadingCopy>
          <ListSkeleton rows={5} />
        </div>
      ) : results.isError && !results.data ? (
        <ErrorState
          title="Search failed"
          description={(results.error as Error)?.message || "Try again in a moment."}
          onRetry={() => results.refetch()}
        />
      ) : (
        <div className="space-y-2">
          <RefetchBar
            active={results.isFetching && !results.isLoading}
            label="Updating results…"
          />
          {(results.data?.hits || []).map((hit) => (
            <NavLink
              key={`${hit.type}-${hit.id}`}
              href={hit.url}
              interactive="card"
              className="mb-2 block rounded-xl"
            >
              <Card className="transition-colors hover:border-primary/40">
                <CardContent className="flex items-start justify-between gap-3 p-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge className="border-border text-muted-foreground">{hit.type}</Badge>
                      <span className="font-medium">{hit.title}</span>
                    </div>
                    {hit.subtitle ? (
                      <p className="mt-1 text-sm text-muted-foreground">{hit.subtitle}</p>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            </NavLink>
          ))}
          {results.isFetched && !results.data?.hits.length ? (
            <p className="text-sm text-muted-foreground">No results for “{debounced}”.</p>
          ) : null}
        </div>
      )}
    </AppShell>
  );
}
