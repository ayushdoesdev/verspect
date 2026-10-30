export type AssistantAvailabilityMessage = {
  kind: "locked" | "unavailable" | "ready";
  title: string;
  detail: string;
  ctaLabel?: string;
};

export function resolveActiveSimulationId({
  activeId,
  storedId,
  simulations,
}: {
  activeId?: string | null;
  storedId?: string | null;
  simulations?: Array<{ id: string }> | null;
}): string | null {
  if (activeId) return activeId;
  if (storedId) return storedId;
  return simulations?.[0]?.id ?? null;
}

export type SimulationLifecycleState = "idle" | "running" | "completed" | "failed" | "cancelled" | "timed_out";

export const DEFAULT_SIMULATION_TIMEOUT_MS = 10 * 60 * 1000;

export function getSimulationLifecycleState({
  status,
  startedAt,
  progress,
  errorMessage,
  timeoutMs = DEFAULT_SIMULATION_TIMEOUT_MS,
  now = Date.now(),
}: {
  status?: string | null;
  startedAt?: string | number | null;
  progress?: number | null;
  errorMessage?: string | null;
  timeoutMs?: number;
  now?: number;
}): {
  state: SimulationLifecycleState;
  title: string;
  detail: string;
  actionLabel: string;
} {
  const normalized = (status || "").toLowerCase();
  if (normalized === "completed") {
    return {
      state: "completed",
      title: "Simulation completed",
      detail: "The upgrade analysis is ready to review.",
      actionLabel: "View report",
    };
  }

  if (startedAt) {
    const startedAtMs = typeof startedAt === "number" ? startedAt : Date.parse(startedAt);
    if (Number.isFinite(startedAtMs) && now - startedAtMs >= timeoutMs) {
      return {
        state: "timed_out",
        title: "Simulation timed out",
        detail: progress && progress > 0
          ? "The analysis stalled while gathering migration details. Retry to continue from a fresh run."
          : "The analysis stalled before it produced a usable result. Retry to continue from a fresh run.",
        actionLabel: "Retry simulation",
      };
    }
  }

  if (normalized === "cancelled" || normalized === "canceled") {
    return {
      state: "cancelled",
      title: "Simulation cancelled",
      detail: "This run was stopped before it could finish. Retry when you are ready.",
      actionLabel: "Retry simulation",
    };
  }

  if (normalized === "failed" || normalized === "timed_out" || normalized === "timeout" || normalized === "stalled") {
    return {
      state: normalized === "timed_out" || normalized === "timeout" || normalized === "stalled" ? "timed_out" : "failed",
      title: normalized === "timed_out" || normalized === "timeout" || normalized === "stalled" ? "Simulation timed out" : "Simulation failed",
      detail:
        normalized === "timed_out" || normalized === "timeout" || normalized === "stalled"
          ? "The analysis stalled before it could finish. Retry to run it again."
          : errorMessage || "The analysis could not be completed. Retry to try again.",
      actionLabel: "Retry simulation",
    };
  }

  if (normalized && !["pending", "queued", "collecting_sources", "analyzing_impact", "generating_plan", "scoring", "preparing", "detecting_api", "matching_rules", "filling_categories", "building_plan", "generating_suggestions", "calculating_confidence", "ai_migration_assistant"].includes(normalized)) {
    return {
      state: "failed",
      title: "Simulation unavailable",
      detail: errorMessage || "The upgrade analysis could not be completed.",
      actionLabel: "Retry simulation",
    };
  }

  return {
    state: "running",
    title: "Simulation in progress",
    detail: "The upgrade analysis is still running in the background.",
    actionLabel: "Cancel simulation",
  };
}

export function getAssistantAvailabilityMessage({
  simCompleted,
  migrationLocked,
  canMigration,
}: {
  simCompleted?: boolean;
  migrationLocked?: boolean;
  canMigration?: boolean;
}): AssistantAvailabilityMessage | null {
  if (migrationLocked) {
    return {
      kind: "locked",
      title: "Upgrade to Team or Enterprise",
      detail:
        "Deterministic analysis completed successfully. The AI Migration Assistant is currently unavailable on your plan, so code patches and line-by-line guidance could not be generated.",
      ctaLabel: "Upgrade to Team",
    };
  }

  if (simCompleted && !canMigration) {
    return {
      kind: "unavailable",
      title: "AI Migration Assistant unavailable",
      detail:
        "Deterministic analysis completed successfully, but the AI Migration Assistant could not generate code patches at this time.",
    };
  }

  return null;
}

export function getSimulationPipelineError(sim?: {
  collected_sources?: Record<string, unknown> | null;
  summary?: string | null;
} | null): string | null {
  const sources = sim?.collected_sources || {};
  const engineError =
    typeof sources.engine_error === "string" ? sources.engine_error : null;
  const aiError =
    typeof sources.ai_assistant_error === "string" ? sources.ai_assistant_error : null;
  return engineError || aiError || null;
}

export const UPGRADE_ANALYSIS_SECTIONS = [
  "Summary",
  "What Changed",
  "Breaking Changes",
  "Affected APIs",
  "Affected Files",
  "Required Changes",
  "Configuration Changes",
  "Migration Rules",
  "Security Impact",
  "Risk",
  "Confidence",
  "Evidence",
  "Sources",
  "Migration Plan",
] as const;

export function formatImpactLimitations(limitations?: string[] | null): string[] {
  return (limitations || []).map((item) => item.trim()).filter((item) => item.length > 0);
}

export const INTELLIGENCE_SCHEMA_VERSION = 2;

export const LEGACY_CATALOG_UNKNOWN_MARKERS = [
  "insufficient deterministic knowledge",
  "insufficient deterministic migration knowledge",
  "no structured migration rules",
  "do not treat as a clean upgrade",
  "do not treat this as a clean upgrade",
] as const;

export type SuggestedChangeStatus =
  | "no_migration_required"
  | "automatic_migration"
  | "manual_review_required"
  | "unknown"
  | "unresolved";

type SuggestedChangeLike = {
  migration_status?: string | null;
  explanation?: string | null;
  status_detail?: string | null;
  status_title?: string | null;
  analysis_source?: string | null;
  unknown?: boolean | null;
  automatic?: boolean;
  confidence?: number;
  current_code?: string | null;
  suggested_code?: string | null;
};

export function isLegacyCatalogUnknown(change: SuggestedChangeLike): boolean {
  if (change.analysis_source) return false;
  if (change.unknown === true) return true;
  const blob = `${change.explanation || ""} ${change.status_detail || ""} ${change.status_title || ""}`.toLowerCase();
  return LEGACY_CATALOG_UNKNOWN_MARKERS.some((marker) => blob.includes(marker));
}

export function isStaleIntelligenceSimulation(sim?: {
  status?: string | null;
  dynamic_intelligence?: { categories?: unknown } | null;
  collected_sources?: Record<string, unknown> | null;
} | null): boolean {
  if (!sim || sim.status !== "completed") return false;
  const sources = sim.collected_sources || {};
  const version = sources.intelligence_schema_version;
  const intel = sim.dynamic_intelligence || (sources.dynamic_intelligence as { categories?: unknown } | undefined);
  if (version === INTELLIGENCE_SCHEMA_VERSION && intel && typeof intel === "object" && intel.categories) {
    return false;
  }
  return true;
}

function normalizeSuggestedSnippet(code?: string | null): string {
  if (!code) return "";
  const skip = [
    "# Manual review required",
    "# Migrate ",
    "# Review ",
    "# Suggested:",
    "# Upgrade ",
  ];
  return code
    .split("\n")
    .map((line) => line.replace(/\s+$/g, ""))
    .filter((line) => !skip.some((prefix) => line.trimStart().startsWith(prefix)))
    .join("\n")
    .trim();
}

export function resolveSuggestedChangeStatus(change: SuggestedChangeLike): SuggestedChangeStatus {
  const status = change.migration_status || "";
  const expl = `${change.explanation || ""} ${change.status_detail || ""}`.toLowerCase();
  // Engine unmatched-usage "no changes" is not a verified clean upgrade.
  if (expl.includes("none match this usage")) {
    return "unresolved";
  }
  if (status === "unresolved") return "unresolved";
  if (change.analysis_source) {
    if (status === "unknown") return "unresolved";
    if (
      status === "automatic_migration" ||
      status === "manual_review_required" ||
      status === "no_migration_required"
    ) {
      return status;
    }
  }
  if (isLegacyCatalogUnknown(change) || status === "unknown") return "unknown";
  if (
    status === "automatic_migration" ||
    status === "manual_review_required" ||
    status === "no_migration_required"
  ) {
    return status;
  }
  const current = normalizeSuggestedSnippet(change.current_code);
  const suggested = normalizeSuggestedSnippet(change.suggested_code);
  const differs = current !== suggested && !!suggested;
  if (expl.includes("insufficient evidence after") || expl.includes("ai-assisted analysis unavailable") || expl.includes("timed out")) {
    return "unresolved";
  }
  if (change.automatic && differs && (change.confidence || 0) >= 0.75) {
    return "automatic_migration";
  }
  if (differs && !change.automatic) return "manual_review_required";
  if (expl.includes("manual")) return "manual_review_required";
  return "unresolved";
}

export function analysisSourceLabel(method?: string | null): string | null {
  if (method === "deterministic+ai") return "Deterministic + AI";
  if (method === "ai") return "AI";
  if (method === "deterministic") return "Deterministic";
  return null;
}
