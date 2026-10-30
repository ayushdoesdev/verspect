import type { EnrichmentProgress } from "./enrichment";
import type { TimelineStep } from "./stages";

export type JobKind = "scan" | "sync" | "simulation" | "import" | "ai_advisor" | "generic";

export type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type BackgroundJob = {
  id: string;
  kind: JobKind;
  title: string;
  subtitle?: string;
  /** Backend resource id (scan id or simulation id). */
  resourceId: string;
  repositoryId?: string;
  organizationId?: string;
  dependencyId?: string;
  status: JobStatus;
  progress: number;
  currentStage?: string | null;
  /** Live per-dependency enrichment progress from the scan worker. */
  enrichment?: EnrichmentProgress | null;
  error?: string | null;
  /**
   * Worker start time from backend `started_at`.
   * Null while queued — UI must show "Waiting for worker..." and not elapsed time.
   */
  backendStartedAt: number | null;
  completedAt?: number;
  /** Soft-hide from panel without removing while still polling briefly. */
  dismissed?: boolean;
  /** Open progress modal for this job. */
  showModal?: boolean;
  /** Client-only steps (import preflight). */
  clientSteps?: TimelineStep[];
  /** Prevent duplicate completion toasts. */
  notified?: boolean;
  workerOffline?: boolean;
  queueBlocked?: boolean;
  /** Waiting far longer than expected — surfaced as "Stalled" with an explanation. */
  stalled?: boolean;
  /** Automatic reclaim after worker death — never show as a hard failure. */
  recovering?: boolean;
  /** 1-based place in the queue while waiting for a worker. */
  queuePosition?: number | null;
  /** Celery worker that claimed the job. */
  workerName?: string | null;
  retryCount?: number;
  /** Last worker liveness signal, used to explain stalls. */
  lastHeartbeatAt?: number | null;
  queuedAt?: number | null;
};

export type ToastTone = "success" | "error" | "info";

export type Toast = {
  id: string;
  title: string;
  description?: string;
  tone: ToastTone;
  actionLabel?: string;
  createdAt: number;
};
