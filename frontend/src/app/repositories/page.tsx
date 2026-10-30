"use client";

import { Suspense, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { GitBranch, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { cn, formatScore } from "@/lib/utils";
import {
  isAnalyzable,
  isUnsupported,
  supportStatusLabel,
} from "@/lib/repository-support";
import { useJobs } from "@/lib/jobs/jobs-context";
import { AppShell, EmptyState, PageHeader } from "@/components/layout/app-shell";
import { PremiumUpgradeModal } from "@/components/billing/premium-gate";
import {
  ErrorState,
  LoadingButton,
  LoadingCopy,
  ListSkeleton,
  RefetchBar,
  RepositoriesSkeleton,
  SessionSkeleton,
} from "@/components/loading";
import { ImportProgressOverlay } from "@/components/loading/import-progress-overlay";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RepositoryActionsMenu } from "@/components/repositories/repository-actions";
import { NavLink } from "@/components/navigation/nav-link";
import type { GitHubRepo, Repository } from "@/types";

type LifecycleFilter = "all" | "active" | "archived";

const LIFECYCLE_FILTERS: { id: LifecycleFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "archived", label: "Archived" },
];

function parseLifecycle(value: string | null): LifecycleFilter {
  if (value === "all" || value === "archived" || value === "active") return value;
  return "active";
}

export default function RepositoriesPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <SessionSkeleton variant="repositories" />
        </AppShell>
      }
    >
      <RepositoriesPageInner />
    </Suspense>
  );
}

function RepositoriesPageInner() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { trackScan, toast } = useJobs();
  const auth = useRequireAuth();
  const entitlements = useEntitlements();
  const [importOpen, setImportOpen] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [importPhase, setImportPhase] = useState<"idle" | "importing" | "handing_off">("idle");

  const lifecycle = parseLifecycle(searchParams.get("lifecycle"));

  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const repos = useQuery({
    queryKey: ["repositories", lifecycle],
    queryFn: () => api.listRepositories({ page_size: 50, lifecycle }),
    enabled: auth.isAuthenticated,
  });
  const ghRepos = useQuery({
    queryKey: ["github-repos"],
    queryFn: api.githubRepos,
    enabled: importOpen,
  });

  const emptyCopy = useMemo(() => {
    if (lifecycle === "archived") {
      return {
        title: "No archived repositories",
        description:
          "Archived repositories stay here with full history. Archive an active repository to move it into this list.",
      };
    }
    if (lifecycle === "all") {
      return {
        title: "No repositories yet",
        description:
          "Connect GitHub to import repositories. Verspect classifies each ecosystem and runs full analysis where supported.",
      };
    }
    return {
      title: "No active repositories",
      description:
        "Import from GitHub, or switch to Archived to find repositories you moved out of the active list.",
    };
  }, [lifecycle]);

  const importMut = useMutation({
    mutationFn: () => api.importRepos(selected),
    onMutate: () => setImportPhase("importing"),
    onSuccess: async (imported) => {
      setImportPhase("handing_off");
      setImportOpen(false);
      setSelected([]);
      qc.invalidateQueries({ queryKey: ["repositories"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      for (const repo of imported) {
        try {
          const scans = await api.scans(`?repository_id=${repo.id}&page_size=1`);
          const scan = scans.items[0];
          if (scan) {
            trackScan(scan.id, {
              kind: "import",
              title: "Import Repository",
              subtitle: repo.full_name,
              repositoryId: repo.id,
              showModal: true,
            });
          }
        } catch {
          /* ignore */
        }
      }
      setImportPhase("idle");
      toast("Import started", {
        tone: "info",
        description: `Analyzing ${imported.length} repositor${imported.length === 1 ? "y" : "ies"}…`,
      });
    },
    onError: (err) => {
      setImportPhase("idle");
      if (err instanceof ApiError && (err.status === 402 || err.status === 403)) {
        setUpgradeOpen(true);
        toast("Upgrade required", {
          tone: "error",
          description: err.detail || "Import requires an active plan.",
          actionLabel: "Upgrade",
        });
        return;
      }
      toast("Unable to connect GitHub", {
        tone: "error",
        description: (err as Error).message || "Import failed",
        actionLabel: "Retry",
      });
    },
  });

  function setLifecycle(next: LifecycleFilter) {
    const params = new URLSearchParams(searchParams.toString());
    if (next === "active") params.delete("lifecycle");
    else params.set("lifecycle", next);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  function openImport() {
    if (!entitlements.canImportRepositories) {
      setUpgradeOpen(true);
      return;
    }
    setImportOpen(true);
  }

  function toggle(id: number) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <SessionSkeleton variant="repositories" />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PremiumUpgradeModal
        open={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        variant={entitlements.evaluationExpired ? "evaluation" : "starter"}
      />
      <ImportProgressOverlay
        open={importPhase !== "idle"}
        phase={importPhase}
        repoCount={selected.length || 1}
      />
      <PageHeader
        title="Repositories"
        description="Import repositories from GitHub. Verspect automatically detects supported ecosystems and provides the appropriate level of analysis."
        actions={
          <Button onClick={openImport}>
            <Plus className="h-4 w-4" /> Import
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {LIFECYCLE_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setLifecycle(f.id)}
            className={cn(
              "rounded-md border px-3 py-2 text-xs font-medium transition-colors",
              lifecycle === f.id
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border text-muted-foreground hover:bg-accent",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {importOpen ? (
        <Card className="mb-6 animate-fade-up">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Select GitHub repositories</CardTitle>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setImportOpen(false)}>
                Cancel
              </Button>
              <LoadingButton
                disabled={selected.length === 0}
                loading={importMut.isPending}
                loadingText="Importing…"
                onClick={() => importMut.mutate()}
              >
                Import {selected.length || ""}
              </LoadingButton>
            </div>
          </CardHeader>
          <CardContent className="max-h-80 space-y-2 overflow-y-auto">
            {ghRepos.isLoading ? (
              <div className="space-y-2 py-2">
                <LoadingCopy>Loading repositories…</LoadingCopy>
                <ListSkeleton rows={4} />
              </div>
            ) : ghRepos.isError ? (
              <ErrorState
                title="Unable to connect GitHub"
                description={(ghRepos.error as Error).message}
                onRetry={() => ghRepos.refetch()}
              />
            ) : (
              (ghRepos.data || []).map((r: GitHubRepo) => (
                <label
                  key={r.github_repo_id}
                  className="flex cursor-pointer items-start gap-3 rounded-md border border-border/60 p-3 hover:bg-accent/40"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    disabled={r.already_imported}
                    checked={selected.includes(r.github_repo_id) || r.already_imported}
                    onChange={() => toggle(r.github_repo_id)}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{r.full_name}</span>
                      {r.already_imported ? (
                        <Badge className="border-success/30 bg-success/10 text-success">Imported</Badge>
                      ) : null}
                      {r.is_private ? (
                        <Badge className="border-border text-muted-foreground">Private</Badge>
                      ) : null}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {r.description || r.language || "No description"}
                    </p>
                  </div>
                </label>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}

      {repos.isLoading && !repos.data ? (
        <div className="space-y-3">
          <LoadingCopy>Loading repositories…</LoadingCopy>
          <RepositoriesSkeleton />
        </div>
      ) : repos.isError && !repos.data ? (
        <ErrorState
          title="Unable to load repositories"
          description={(repos.error as Error)?.message || "Try again in a moment."}
          onRetry={() => repos.refetch()}
        />
      ) : !repos.data?.items.length ? (
        <EmptyState
          title={emptyCopy.title}
          description={emptyCopy.description}
          icon={<GitBranch className="h-6 w-6" />}
          action={
            lifecycle === "archived" ? (
              <Button variant="outline" onClick={() => setLifecycle("active")}>
                View active
              </Button>
            ) : (
              <Button onClick={openImport}>Connect GitHub</Button>
            )
          }
        />
      ) : (
        <div className="grid gap-3">
          <RefetchBar
            active={repos.isFetching && !repos.isLoading}
            label="Updating repositories…"
          />
          {repos.data.items.map((repo) => (
            <RepositoryListCard key={repo.id} repo={repo} />
          ))}
        </div>
      )}
    </AppShell>
  );
}

function RepositoryListCard({ repo }: { repo: Repository }) {
  const unsupported = isUnsupported(repo);
  const statusLabel = supportStatusLabel(repo);
  const archived = !!repo.is_archived;
  return (
    <Card
      className={cn(
        "transition-colors hover:border-primary/40",
        archived && "border-border/70 bg-muted/20",
      )}
    >
      <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <NavLink
          href={`/repositories/${repo.id}`}
          interactive="card"
          className="min-w-0 flex-1 rounded-md"
        >
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate font-semibold">{repo.full_name}</h3>
            {archived ? (
              <Badge className="border-warning/35 bg-warning/10 text-warning">Archived</Badge>
            ) : null}
            <Badge className="border-border text-muted-foreground">{repo.sync_status}</Badge>
            {!archived && !repo.is_watching ? (
              <Badge className="border-border text-muted-foreground">Paused</Badge>
            ) : null}
            {(repo.detected_language || repo.language) ? (
              <Badge className="border-primary/30 bg-primary/10 text-primary">
                {repo.detected_language || repo.language}
              </Badge>
            ) : null}
            {statusLabel ? (
              <Badge
                className={
                  isAnalyzable(repo)
                    ? "border-success/40 bg-success/10 text-success"
                    : "border-primary/25 bg-primary/10 text-primary"
                }
              >
                {statusLabel}
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">
            {archived
              ? "Archived · read-only · historical analysis retained"
              : repo.description ||
                (unsupported
                  ? "Classified · full analysis planned for this ecosystem"
                  : "No description")}
          </p>
        </NavLink>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          {unsupported ? (
            <>
              <Stat label="Deps" value="—" />
              <Stat label="Outdated" value="—" />
              <Stat label="Security" value="—" />
              <Stat label="Health" value="—" />
            </>
          ) : (
            <>
              <Stat label="Deps" value={repo.dependency_count} />
              <Stat label="Outdated" value={repo.outdated_count} />
              <Stat label="Vulns" value={repo.vulnerable_count} />
              <Stat label="Health" value={formatScore(repo.health_score)} />
            </>
          )}
          <div onClick={(e) => e.preventDefault()}>
            <RepositoryActionsMenu repo={repo} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}
