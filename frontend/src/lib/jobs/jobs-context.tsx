"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
import { useAuthOptional } from "@/lib/auth-context";
import type { Paginated, Repository, WorkerStatus } from "@/types";
import type { BackgroundJob, JobKind, Toast, ToastTone } from "./types";
import {
  mapSimulationJobStatus,
  parseBackendTime,
  scanToJobFields,
} from "./status";

const LEGACY_STORAGE_KEY = "depintel.background-jobs.v1";

/** Progress poll cadence. Fast enough to feel live, slow enough to stay cheap. */
const POLL_INTERVAL_MS = 2500;

/**
 * A job waiting longer than this without a worker is reported as "Stalled".
 * Purely advisory: the backend still owns the decision to fail the job.
 */
const STALL_AFTER_MS = 120_000;

const OFFLINE_WORKER_STATUS: WorkerStatus = {
  online: false,
  status: "offline",
  active_workers: 0,
  workers: [],
  active_tasks: 0,
  reserved_tasks: 0,
  queue_depths: {},
  queued_total: 0,
  queue_blocked: false,
  message: "Background processing service is unavailable.",
  detail: null,
  heartbeat_seconds: 15,
  pickup_timeout_seconds: 60,
  stale_timeout_minutes: 5,
};

type StartJobInput = {
  kind: JobKind;
  title: string;
  subtitle?: string;
  resourceId: string;
  repositoryId?: string;
  organizationId?: string;
  dependencyId?: string;
  showModal?: boolean;
};

type JobsContextValue = {
  jobs: BackgroundJob[];
  activeJobs: BackgroundJob[];
  modalJob: BackgroundJob | null;
  toasts: Toast[];
  ready: boolean;
  /** Null until the first health probe resolves. */
  workerStatus: WorkerStatus | null;
  startJob: (input: StartJobInput) => string;
  trackScan: (scanId: string, opts?: Partial<StartJobInput>) => string;
  trackSimulation: (
    simulationId: string,
    dependencyId: string,
    opts?: Partial<StartJobInput>,
  ) => string;
  updateJob: (id: string, patch: Partial<BackgroundJob>) => void;
  removeJob: (id: string) => void;
  removeJobsForRepository: (repositoryId: string) => void;
  dismissJob: (id: string) => void;
  setModalJob: (id: string | null) => void;
  refreshActiveJobs: () => Promise<void>;
  cancelJobScan: (scanId: string) => Promise<void>;
  retryJobScan: (scanId: string) => Promise<void>;
  cancelJobSimulation: (dependencyId: string, simulationId: string) => Promise<void>;
  retryJobSimulation: (dependencyId: string, simulationId: string) => Promise<void>;
  toast: (title: string, opts?: { description?: string; tone?: ToastTone; actionLabel?: string }) => void;
  dismissToast: (id: string) => void;
};

const JobsContext = createContext<JobsContextValue | null>(null);

function clearLegacyStorage() {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function jobIdFor(kind: JobKind, resourceId: string) {
  return `${kind}-${resourceId}`;
}

/**
 * After a Repository Scan finishes, refresh repository-backed screens.
 * Job polling alone only updates job state — React Query still holds the
 * pre-scan Repository snapshot (deps/outdated/vulns/health = 0).
 */
async function syncRepositoryQueries(
  queryClient: QueryClient,
  repositoryId: string,
): Promise<void> {
  try {
    const repo = await api.repository(repositoryId);
    queryClient.setQueryData<Repository>(["repository", repositoryId], repo);
    queryClient.setQueriesData<Paginated<Repository>>(
      { queryKey: ["repositories"] },
      (current) => {
        if (!current?.items) return current;
        let touched = false;
        const items = current.items.map((item) => {
          if (item.id !== repositoryId) return item;
          touched = true;
          return repo;
        });
        return touched ? { ...current, items } : current;
      },
    );
  } catch {
    /* invalidate below still reconciles */
  }

  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["repositories"] }),
    queryClient.invalidateQueries({ queryKey: ["repository", repositoryId] }),
    queryClient.invalidateQueries({ queryKey: ["repo-deps", repositoryId] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    queryClient.invalidateQueries({ queryKey: ["dependencies"] }),
    queryClient.invalidateQueries({ queryKey: ["dependency"] }),
    queryClient.invalidateQueries({ queryKey: ["security"] }),
    queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  ]);
}

export function JobsProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const queryClient = useQueryClient();
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [ready, setReady] = useState(false);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null);
  const polling = useRef(false);
  const jobsRef = useRef<BackgroundJob[]>([]);
  const notifiedRef = useRef<Set<string>>(new Set());
  const repoSyncRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  const updateJob = useCallback((id: string, patch: Partial<BackgroundJob>) => {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...patch } : j)));
  }, []);

  const removeJob = useCallback((id: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
  }, []);

  const removeJobsForRepository = useCallback((repositoryId: string) => {
    setJobs((prev) => prev.filter((j) => j.repositoryId !== repositoryId));
  }, []);

  const toast = useCallback(
    (
      title: string,
      opts?: { description?: string; tone?: ToastTone; actionLabel?: string },
    ) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) =>
        [
          {
            id,
            title,
            description: opts?.description,
            tone: opts?.tone || "info",
            actionLabel: opts?.actionLabel,
            createdAt: Date.now(),
          },
          ...prev,
        ].slice(0, 5),
      );
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 5500);
    },
    [],
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const refreshActiveJobs = useCallback(async () => {
    clearLegacyStorage();
    // Never probe /auth/me while logged out — that used to 401 and wipe fresh tokens
    if (!auth || auth.status !== "authenticated") {
      setJobs([]);
      setReady(true);
      return;
    }
    try {
      const activeOrg = auth.user?.active_organization_id || null;
      setOrgId(activeOrg);

      const [scansPage, reposPage] = await Promise.all([
        api.scans("?active_only=true&page_size=50"),
        api.repositories("?page_size=100"),
      ]);

      const repoNames = new Map(
        (reposPage.items || []).map((r) => [r.id, r.full_name] as const),
      );
      const repoIds = new Set((reposPage.items || []).map((r) => r.id));

      setJobs((prev) => {
        const uiByResource = new Map(
          prev.map((j) => [j.resourceId, { showModal: j.showModal, kind: j.kind, title: j.title }] as const),
        );

        const next: BackgroundJob[] = [];

        for (const scan of scansPage.items || []) {
          if (!repoIds.has(scan.repository_id)) continue;

          const fields = scanToJobFields(scan);
          if (
            fields.status === "completed" ||
            fields.status === "failed" ||
            fields.status === "cancelled"
          ) {
            continue;
          }

          const prevUi = uiByResource.get(scan.id);
          const isAiAdvisor =
            scan.scan_type === "ai_advisor" ||
            (scan.summary as { kind?: string } | null | undefined)?.kind === "ai_upgrade_advisor";
          const kind: JobKind = isAiAdvisor
            ? "ai_advisor"
            : prevUi?.kind === "sync" || prevUi?.kind === "import" || prevUi?.kind === "ai_advisor"
              ? (prevUi.kind as JobKind)
              : "scan";
          next.push({
            id: jobIdFor(kind, scan.id),
            kind,
            title:
              kind === "ai_advisor"
                ? "AI Upgrade Advisor"
                : kind === "sync"
                  ? "Syncing Repository…"
                  : kind === "import"
                    ? "Import Repository"
                    : "Repository Scan",
            subtitle: repoNames.get(scan.repository_id) || prevUi?.title,
            resourceId: scan.id,
            organizationId: activeOrg || undefined,
            ...fields,
            repositoryId: scan.repository_id,
            showModal: prevUi?.showModal ?? false,
            dismissed: false,
            notified: notifiedRef.current.has(scan.id),
          });
        }

        for (const j of prev) {
          if (j.kind !== "simulation") continue;
          if (j.status === "completed" || j.status === "failed" || j.status === "cancelled") {
            continue;
          }
          if (activeOrg && j.organizationId && j.organizationId !== activeOrg) continue;
          next.push({ ...j, organizationId: activeOrg || j.organizationId });
        }

        return next;
      });
    } catch {
      setJobs([]);
    } finally {
      setReady(true);
    }
  }, [auth]);

  // Hydrate from backend once authenticated
  useEffect(() => {
    clearLegacyStorage();
    if (!auth || auth.status === "loading") return;
    void refreshActiveJobs();
    // auth object identity changes; status + user id are the meaningful triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth?.status, auth?.user?.id, refreshActiveJobs]);

  // Re-hydrate when org switches or window focuses
  useEffect(() => {
    const onFocus = () => {
      void refreshActiveJobs();
    };
    const onOrg = () => {
      void refreshActiveJobs();
    };
    const onRepoDeleted = (event: Event) => {
      const detail = (event as CustomEvent<{ repositoryId?: string }>).detail;
      if (detail?.repositoryId) removeJobsForRepository(detail.repositoryId);
    };
    window.addEventListener("focus", onFocus);
    window.addEventListener("depintel:org-switched", onOrg);
    window.addEventListener("depintel:repository-deleted", onRepoDeleted);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("depintel:org-switched", onOrg);
      window.removeEventListener("depintel:repository-deleted", onRepoDeleted);
    };
  }, [refreshActiveJobs, removeJobsForRepository]);

  const startJob = useCallback((input: StartJobInput) => {
    const id = jobIdFor(input.kind, input.resourceId);
    setJobs((prev) => {
      const existing = prev.find((j) => j.resourceId === input.resourceId);
      if (existing) {
        return prev.map((j) =>
          j.resourceId === input.resourceId
            ? {
                ...j,
                ...input,
                id,
                status: j.status === "pending" ? "pending" : j.status,
                showModal: input.showModal ?? j.showModal,
                dismissed: false,
                backendStartedAt: j.backendStartedAt,
              }
            : j,
        );
      }
      const job: BackgroundJob = {
        id,
        kind: input.kind,
        title: input.title,
        subtitle: input.subtitle,
        resourceId: input.resourceId,
        repositoryId: input.repositoryId,
        organizationId: input.organizationId || orgId || undefined,
        dependencyId: input.dependencyId,
        status: "pending",
        progress: 0,
        currentStage: "queued",
        backendStartedAt: null,
        showModal: input.showModal ?? true,
        dismissed: false,
      };
      return [job, ...prev.filter((j) => j.resourceId !== input.resourceId)];
    });
    return id;
  }, [orgId]);

  const trackScan = useCallback(
    (scanId: string, opts: Partial<StartJobInput> = {}) =>
      startJob({
        kind: opts.kind || "scan",
        title: opts.title || "Repository Scan",
        subtitle: opts.subtitle,
        resourceId: scanId,
        repositoryId: opts.repositoryId,
        organizationId: opts.organizationId || orgId || undefined,
        showModal: opts.showModal ?? true,
      }),
    [orgId, startJob],
  );

  const trackSimulation = useCallback(
    (simulationId: string, dependencyId: string, opts: Partial<StartJobInput> = {}) =>
      startJob({
        kind: "simulation",
        title: opts.title || "Upgrade Simulation",
        subtitle: opts.subtitle,
        resourceId: simulationId,
        dependencyId,
        repositoryId: opts.repositoryId,
        organizationId: opts.organizationId || orgId || undefined,
        showModal: opts.showModal ?? false,
      }),
    [orgId, startJob],
  );

  const dismissJob = useCallback((id: string) => {
    // Soft-dismiss: hide from the panel but keep polling until terminal so
    // repository caches still sync when the scan finishes.
    setJobs((prev) =>
      prev.map((j) =>
        j.id === id
          ? { ...j, dismissed: true, showModal: false }
          : j,
      ),
    );
  }, []);

  const setModalJob = useCallback((id: string | null) => {
    setJobs((prev) =>
      prev.map((j) => ({
        ...j,
        showModal: id ? j.id === id : false,
      })),
    );
  }, []);

  const cancelJobScan = useCallback(
    async (scanId: string) => {
      try {
        const updated = await api.cancelScan(scanId);
        const target = jobsRef.current.find((j) => j.resourceId === scanId);
        const targetId = target?.id || jobIdFor("scan", scanId);
        updateJob(targetId, {
          status: "cancelled",
          currentStage: "cancelled",
          error: updated.error_message || "Scan cancelled by user",
        });
        toast("Scan cancelled", { tone: "info" });
      } catch (err) {
        toast("Failed to cancel scan", { tone: "error", description: (err as Error).message });
      }
    },
    [toast, updateJob],
  );

  const retryJobScan = useCallback(
    async (scanId: string) => {
      try {
        const updated = await api.retryScan(scanId);
        // The job may be tracked under any scan-like kind (scan/sync/import).
        const target = jobsRef.current.find((j) => j.resourceId === scanId);
        const targetId = target?.id || jobIdFor("scan", scanId);
        notifiedRef.current.delete(scanId);
        updateJob(targetId, {
          status: "pending",
          progress: 0,
          currentStage: "queued",
          error: null,
          backendStartedAt: null,
          completedAt: undefined,
          notified: false,
          workerOffline: false,
          queueBlocked: false,
          stalled: false,
          retryCount: updated.retry_count ?? (target?.retryCount ?? 0) + 1,
          queuedAt: parseBackendTime(updated.queued_at) ?? Date.now(),
          workerName: null,
        });
        toast("Scan restarted", { tone: "info", description: "Running again from stage one" });
      } catch (err) {
        toast("Failed to retry scan", { tone: "error", description: (err as Error).message });
      }
    },
    [toast, updateJob],
  );

  const cancelJobSimulation = useCallback(
    async (dependencyId: string, simulationId: string) => {
      try {
        await api.cancelSimulation(dependencyId, simulationId);
        notifiedRef.current.add(simulationId);
        updateJob(jobIdFor("simulation", simulationId), {
          status: "cancelled",
          currentStage: "cancelled",
          error: "Simulation cancelled by user",
        });
        toast("Simulation cancelled", { tone: "info" });
      } catch (err) {
        toast("Failed to cancel simulation", {
          tone: "error",
          description: (err as Error).message,
        });
      }
    },
    [toast, updateJob],
  );

  const retryJobSimulation = useCallback(
    async (dependencyId: string, simulationId: string) => {
      try {
        const updated = await api.retrySimulation(dependencyId, simulationId);
        notifiedRef.current.delete(simulationId);
        updateJob(jobIdFor("simulation", simulationId), {
          status: "pending",
          progress: 0,
          currentStage: "queued",
          error: null,
          backendStartedAt: null,
          completedAt: undefined,
          notified: false,
          workerOffline: false,
          queueBlocked: false,
          stalled: false,
          retryCount: updated.retry_count ?? 0,
          workerName: null,
        });
        toast("Simulation restarted", { tone: "info" });
      } catch (err) {
        toast("Failed to retry simulation", {
          tone: "error",
          description: (err as Error).message,
        });
      }
    },
    [toast, updateJob],
  );

  const activeKey = jobs
    .filter((j) => j.status === "running" || j.status === "pending")
    .map((j) => j.id)
    .join(",");

  useEffect(() => {
    if (!activeKey) return;
    let cancelled = false;

    async function tick() {
      if (polling.current || cancelled) return;
      polling.current = true;
      const active = jobsRef.current.filter(
        (j) => j.status === "running" || j.status === "pending",
      );
      try {
        let health: WorkerStatus;
        try {
          health = await api.getWorkerStatus();
        } catch {
          health = OFFLINE_WORKER_STATUS;
        }
        setWorkerStatus(health);
        const workerOffline = !health.online;

        await Promise.all(
          active.map(async (job) => {
            try {
              if (
                job.kind === "scan" ||
                job.kind === "sync" ||
                job.kind === "import" ||
                job.kind === "ai_advisor"
              ) {
                let scan;
                try {
                  scan = await api.getScan(job.resourceId);
                } catch (err) {
                  if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
                    removeJob(job.id);
                  }
                  return;
                }
                const fields = scanToJobFields(scan);
                const nextStatus = fields.status;
                const terminal =
                  nextStatus === "completed" ||
                  nextStatus === "failed" ||
                  nextStatus === "cancelled";
                const shouldNotify = terminal && !notifiedRef.current.has(job.resourceId);

                if (terminal) {
                  notifiedRef.current.add(job.resourceId);

                  // Repository Scan / import / sync — refresh cards after terminal.
                  // AI Upgrade Advisor does not own repository aggregate stats.
                  if (
                    job.kind !== "ai_advisor" &&
                    !repoSyncRef.current.has(job.resourceId)
                  ) {
                    const repositoryId =
                      scan.repository_id || job.repositoryId || undefined;
                    if (repositoryId) {
                      repoSyncRef.current.add(job.resourceId);
                      void syncRepositoryQueries(queryClient, repositoryId);
                    }
                  }

                  if (shouldNotify) {
                    if (nextStatus === "completed") {
                      if (job.kind === "ai_advisor") {
                        toast("AI Upgrade Advisor finished", {
                          tone: "success",
                          description: job.subtitle || "Recommendations are ready",
                        });
                      } else {
                        toast(
                          job.kind === "sync"
                            ? "Repository synchronized"
                            : job.kind === "import"
                              ? "Repository imported successfully"
                              : "Repository scan completed",
                          { tone: "success", description: job.subtitle || job.title },
                        );
                        // Kick off / track independent AI job if the scan enqueued one
                        const aiId = (scan.summary as { ai_advisor_scan_id?: string } | null)
                          ?.ai_advisor_scan_id;
                        if (aiId) {
                          startJob({
                            kind: "ai_advisor",
                            title: "AI Upgrade Advisor",
                            subtitle: job.subtitle,
                            resourceId: aiId,
                            repositoryId: scan.repository_id,
                            showModal: false,
                          });
                        }
                      }
                    } else if (nextStatus === "cancelled") {
                      toast(
                        job.kind === "ai_advisor" ? "AI Advisor cancelled" : "Scan cancelled",
                        { tone: "info", description: job.subtitle },
                      );
                    } else {
                      toast(
                        job.kind === "ai_advisor"
                          ? "AI Advisor failed"
                          : job.kind === "sync"
                            ? "Sync failed"
                            : "Scan failed",
                        {
                          tone: "error",
                          description: scan.error_message || "Something went wrong",
                          actionLabel: job.kind === "import" ? "Retry Import" : "Retry",
                        },
                      );
                    }
                  }
                  if (!job.showModal) {
                    removeJob(job.id);
                  } else {
                    updateJob(job.id, {
                      ...fields,
                      completedAt: Date.now(),
                      notified: true,
                      workerOffline: false,
                      queueBlocked: false,
                      stalled: false,
                    });
                  }
                  return;
                }

                // A job that is still waiting past the stall threshold gets an
                // explanation rather than an unchanging "Queued" label.
                const waitingSince = fields.queuedAt ?? parseBackendTime(scan.created_at);
                const stalled =
                  nextStatus === "pending" &&
                  !!waitingSince &&
                  Date.now() - waitingSince > STALL_AFTER_MS;

                updateJob(job.id, {
                  ...fields,
                  repositoryId: scan.repository_id,
                  workerOffline: nextStatus === "pending" && workerOffline,
                  queueBlocked:
                    nextStatus === "pending" && !workerOffline && health.queue_blocked,
                  stalled,
                });
              } else if (job.kind === "simulation" && job.dependencyId) {
                let sim;
                try {
                  sim = await api.getSimulation(job.dependencyId, job.resourceId);
                } catch (err) {
                  if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
                    removeJob(job.id);
                  }
                  return;
                }
                const nextStatus = mapSimulationJobStatus(sim.status);
                const backendStartedAt = parseBackendTime(sim.started_at);
                const terminal =
                  nextStatus === "completed" ||
                  nextStatus === "failed" ||
                  nextStatus === "cancelled";
                const shouldNotify = terminal && !notifiedRef.current.has(job.resourceId);

                const simFields = {
                  progress: sim.progress_percent,
                  currentStage: sim.current_stage || sim.status,
                  status: nextStatus,
                  error: sim.error_message,
                  backendStartedAt,
                  workerName: sim.worker_name ?? null,
                  retryCount: sim.retry_count ?? 0,
                  lastHeartbeatAt: parseBackendTime(sim.last_heartbeat_at),
                  queuedAt: parseBackendTime(sim.queued_at ?? sim.created_at),
                };

                if (terminal) {
                  notifiedRef.current.add(job.resourceId);
                  if (shouldNotify) {
                    if (nextStatus === "completed") {
                      toast("Upgrade completed", {
                        tone: "success",
                        description: `${sim.package_name} ${sim.from_version} → ${sim.to_version}`,
                      });
                    } else if (nextStatus === "cancelled") {
                      toast("Simulation cancelled", {
                        tone: "info",
                        description: `${sim.package_name} ${sim.from_version} → ${sim.to_version}`,
                      });
                    } else {
                      toast("Upgrade simulation failed", {
                        tone: "error",
                        description: sim.error_message || "AI unavailable or engine error",
                        actionLabel: "Retry",
                      });
                    }
                  }
                  if (!job.showModal) {
                    removeJob(job.id);
                  } else {
                    updateJob(job.id, {
                      ...simFields,
                      completedAt: Date.now(),
                      notified: true,
                      workerOffline: false,
                      queueBlocked: false,
                      stalled: false,
                    });
                  }
                  return;
                }

                const simWaitingSince =
                  simFields.queuedAt ?? parseBackendTime(sim.created_at);
                updateJob(job.id, {
                  ...simFields,
                  workerOffline: nextStatus === "pending" && workerOffline,
                  queueBlocked:
                    nextStatus === "pending" && !workerOffline && health.queue_blocked,
                  stalled:
                    nextStatus === "pending" &&
                    !!simWaitingSince &&
                    Date.now() - simWaitingSince > STALL_AFTER_MS,
                });
              }
            } catch {
              /* keep polling */
            }
          }),
        );
      } finally {
        polling.current = false;
      }
    }

    tick();
    const interval = window.setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [activeKey, queryClient, removeJob, startJob, toast, updateJob]);

  // Keep worker health fresh even with no active jobs so a newly started scan
  // can immediately explain an offline worker instead of appearing to hang.
  useEffect(() => {
    if (!auth || auth.status !== "authenticated") return;
    let cancelled = false;
    async function probe() {
      try {
        const health = await api.getWorkerStatus();
        if (!cancelled) setWorkerStatus(health);
      } catch {
        if (!cancelled) setWorkerStatus(OFFLINE_WORKER_STATUS);
      }
    }
    void probe();
    const interval = window.setInterval(probe, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [auth?.status]); // eslint-disable-line react-hooks/exhaustive-deps -- probe on auth status only

  const activeJobs = useMemo(
    () =>
      jobs.filter(
        (j) =>
          !j.dismissed &&
          (j.status === "running" || j.status === "pending") &&
          (!orgId || !j.organizationId || j.organizationId === orgId),
      ),
    [jobs, orgId],
  );

  const modalJob = useMemo(
    () => jobs.find((j) => j.showModal && !j.dismissed) || null,
    [jobs],
  );

  const value = useMemo(
    () => ({
      jobs,
      activeJobs,
      modalJob,
      toasts,
      ready,
      workerStatus,
      startJob,
      trackScan,
      trackSimulation,
      updateJob,
      removeJob,
      removeJobsForRepository,
      dismissJob,
      setModalJob,
      refreshActiveJobs,
      cancelJobScan,
      retryJobScan,
      cancelJobSimulation,
      retryJobSimulation,
      toast,
      dismissToast,
    }),
    [
      jobs,
      activeJobs,
      modalJob,
      toasts,
      ready,
      workerStatus,
      startJob,
      trackScan,
      trackSimulation,
      updateJob,
      removeJob,
      removeJobsForRepository,
      dismissJob,
      setModalJob,
      refreshActiveJobs,
      cancelJobScan,
      retryJobScan,
      cancelJobSimulation,
      retryJobSimulation,
      toast,
      dismissToast,
    ],
  );

  return <JobsContext.Provider value={value}>{children}</JobsContext.Provider>;
}

export function useJobs() {
  const ctx = useContext(JobsContext);
  if (!ctx) throw new Error("useJobs must be used within JobsProvider");
  return ctx;
}

export function useJobsOptional() {
  return useContext(JobsContext);
}
