import type { Scan } from "@/types";
import { parseEnrichment } from "./enrichment";
import type { JobStatus } from "./types";

/** Backend statuses that mean "waiting in queue". */
export const PENDING_SCAN_STATUSES = new Set(["pending", "queued"]);

/** Backend statuses that mean the worker has started. */
export const RUNNING_SCAN_STATUSES = new Set([
  "running",
  "cloning",
  "classifying",
  "scanning_manifests",
  "parsing_ast",
  "checking_versions",
  "checking_vulnerabilities",
  "checking_licenses",
  "scoring_health",
  "analyzing_ai",
]);

export const TERMINAL_SCAN_STATUSES = new Set(["completed", "failed", "cancelled"]);

export const PENDING_SIM_STATUSES = new Set(["pending", "queued"]);

export const RUNNING_SIM_STATUSES = new Set([
  "collecting_sources",
  "analyzing_impact",
  "generating_plan",
  "scoring",
  "preparing",
  "detecting_api",
  "matching_rules",
  "filling_categories",
  "building_plan",
  "generating_suggestions",
  "calculating_confidence",
]);

export const TERMINAL_SIM_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function mapScanJobStatus(backendStatus: string): JobStatus {
  const s = (backendStatus || "").toLowerCase();
  if (s === "cancelled") return "cancelled";
  if (TERMINAL_SCAN_STATUSES.has(s)) {
    return s === "completed" ? "completed" : "failed";
  }
  if (PENDING_SCAN_STATUSES.has(s)) return "pending";
  if (RUNNING_SCAN_STATUSES.has(s)) return "running";
  // Unknown mid-pipeline stage → treat as running if not terminal
  return "running";
}

export function mapSimulationJobStatus(backendStatus: string): JobStatus {
  const s = (backendStatus || "").toLowerCase();
  if (s === "cancelled") return "cancelled";
  if (TERMINAL_SIM_STATUSES.has(s)) {
    return s === "completed" ? "completed" : "failed";
  }
  if (PENDING_SIM_STATUSES.has(s)) return "pending";
  return "running";
}

export function parseBackendTime(value?: string | null): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

const RECOVERING_MESSAGE = "Recovering scan...";

export function isScanRecovering(
  scan: Pick<Scan, "current_stage" | "error_message" | "status" | "extra_metadata">,
): boolean {
  const stage = (scan.current_stage || "").toLowerCase();
  if (stage === "recovering") return true;
  if ((scan.error_message || "") === RECOVERING_MESSAGE) return true;
  const recovery = (scan.extra_metadata as { recovery?: { recovered_from_worker_failure?: boolean } } | null)
    ?.recovery;
  const recovered = !!recovery?.recovered_from_worker_failure;
  const pending =
    (scan.status || "").toLowerCase() === "queued" ||
    (scan.status || "").toLowerCase() === "pending";
  return recovered && pending;
}

export function scanToJobFields(scan: Scan) {
  const status = mapScanJobStatus(scan.status);
  const recovering = isScanRecovering(scan);
  return {
    progress: scan.progress_percent ?? 0,
    currentStage: recovering ? "recovering" : scan.current_stage || scan.status,
    enrichment: parseEnrichment(scan.extra_metadata, scan.summary),
    status,
    // Never surface the recovery banner as a terminal error string.
    error: recovering ? null : scan.error_message,
    recovering,
    backendStartedAt: parseBackendTime(scan.started_at),
    repositoryId: scan.repository_id,
    queuePosition: scan.queue_position ?? null,
    workerName: scan.worker_name ?? null,
    retryCount: scan.retry_count ?? 0,
    lastHeartbeatAt: parseBackendTime(scan.last_heartbeat_at),
    queuedAt: parseBackendTime(scan.queued_at ?? scan.created_at),
  };
}

/**
 * Human status shown in the modal and jobs panel.
 *
 * Order matters: infrastructure problems outrank job state, because "Worker
 * Offline" explains a stuck job better than "Queued" does.
 */
export function jobStatusLabel(job: {
  status: JobStatus;
  workerOffline?: boolean;
  queueBlocked?: boolean;
  stalled?: boolean;
  recovering?: boolean;
  currentStage?: string | null;
  backendStartedAt?: number | null;
  progress?: number;
}): string {
  if (job.recovering || (job.currentStage || "").toLowerCase() === "recovering") {
    return "Recovering scan…";
  }
  if (job.workerOffline) return "Worker Offline";
  switch (job.status) {
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    case "pending":
      if (job.stalled) return "Stalled";
      if (job.queueBlocked) return "Queue Blocked";
      return job.backendStartedAt ? "Preparing repository" : "Waiting for worker";
    case "running":
      if (job.stalled) return "Stalled";
      if ((job.currentStage || "").toLowerCase() === "queued") return "Preparing repository";
      if ((job.progress ?? 0) >= 95) return "Finishing";
      return "Scanning";
    default:
      return "Queued";
  }
}
