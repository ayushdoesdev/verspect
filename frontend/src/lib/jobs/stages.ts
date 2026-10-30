export type StageDef = {
  key: string;
  label: string;
  copy: string;
};

/** Maps backend scan.current_stage values → ordered UI timeline (deterministic only). */
export const SCAN_STAGES: StageDef[] = [
  { key: "queued", label: "Queued", copy: "Waiting in queue…" },
  { key: "recovering", label: "Recovering", copy: "Recovering scan…" },
  { key: "cloning", label: "Cloning Repository", copy: "Cloning repository…" },
  { key: "classifying", label: "Classifying Repository", copy: "Detecting language and package manager…" },
  { key: "files", label: "Reading Files", copy: "Reading repository files…" },
  { key: "ast", label: "Parsing AST", copy: "Parsing AST…" },
  { key: "manifests", label: "Detecting Dependencies", copy: "Detecting dependencies…" },
  { key: "graph", label: "Building Dependency Graph", copy: "Building dependency graph…" },
  { key: "versions", label: "Version Analysis", copy: "Checking package versions…" },
  { key: "vulnerabilities", label: "Security Scan", copy: "Scanning vulnerabilities…" },
  {
    key: "knowledge",
    label: "Building Dependency Intelligence",
    copy: "Checking package versions…",
  },
  { key: "health", label: "Health Scoring", copy: "Scoring repository health…" },
  { key: "completed", label: "Done", copy: "Repository imported successfully" },
];

export const SYNC_STAGES: StageDef[] = [
  { key: "queued", label: "Queued", copy: "Preparing sync…" },
  { key: "recovering", label: "Recovering", copy: "Recovering scan…" },
  { key: "cloning", label: "Cloning Repository", copy: "Fetching latest commits…" },
  { key: "classifying", label: "Classifying Repository", copy: "Detecting language and package manager…" },
  { key: "files", label: "Reading Files", copy: "Reading repository files…" },
  { key: "ast", label: "Parsing AST", copy: "Re-parsing changed modules…" },
  { key: "manifests", label: "Detecting Dependencies", copy: "Detecting dependency changes…" },
  { key: "graph", label: "Building Dependency Graph", copy: "Updating dependency graph…" },
  { key: "versions", label: "Version Analysis", copy: "Checking package versions…" },
  { key: "vulnerabilities", label: "Security Scan", copy: "Scanning vulnerabilities…" },
  {
    key: "knowledge",
    label: "Building Dependency Intelligence",
    copy: "Checking package versions…",
  },
  { key: "health", label: "Health Scoring", copy: "Updating health scores…" },
  { key: "completed", label: "Done", copy: "Sync finished" },
];

/** Independent AI Upgrade Advisor job (never part of Repository Scan). */
export const AI_ADVISOR_STAGES: StageDef[] = [
  { key: "queued", label: "Queued", copy: "Waiting to start AI Upgrade Advisor…" },
  { key: "preparing", label: "Preparing Context", copy: "Loading repository intelligence…" },
  { key: "analyzing", label: "Analyzing Dependencies", copy: "AI Upgrade Advisor is analyzing dependencies…" },
  { key: "generating", label: "Generating Recommendations", copy: "Generating upgrade recommendations…" },
  { key: "saving", label: "Saving Results", copy: "Saving AI recommendations…" },
  { key: "completed", label: "Done", copy: "AI recommendations ready" },
];

export const IMPORT_PRE_STAGES: StageDef[] = [
  { key: "auth", label: "Authentication", copy: "Connected to GitHub" },
  { key: "fetch", label: "Fetching repositories", copy: "Loading your GitHub repositories…" },
  { key: "metadata", label: "Importing metadata", copy: "Creating project records…" },
];

export const SIMULATION_STAGES: StageDef[] = [
  { key: "queued", label: "Preparing Simulation", copy: "Queuing upgrade simulation…" },
  { key: "preparing", label: "Preparing Simulation", copy: "Reading dependency versions…" },
  { key: "detecting_api", label: "Analyzing API Usage", copy: "Understanding API usage…" },
  { key: "matching_rules", label: "Checking Migration Rules", copy: "Matching migration rules…" },
  { key: "filling_categories", label: "Upgrade Intelligence", copy: "Filling analysis categories…" },
  { key: "building_plan", label: "Building Upgrade Plan", copy: "Calculating affected files…" },
  { key: "generating_suggestions", label: "Generating Suggestions", copy: "Generating upgrade recommendations…" },
  { key: "ai_migration_assistant", label: "AI Migration Assistant", copy: "Generating exact migration patches…" },
  { key: "calculating_confidence", label: "Calculating Confidence", copy: "Estimating migration effort…" },
  { key: "completed", label: "Done", copy: "Upgrade report ready" },
  // legacy aliases still emitted by older workers
  { key: "collecting_sources", label: "Analyzing API Usage", copy: "Collecting migration sources…" },
  { key: "learning_rules", label: "Checking Migration Rules", copy: "Learning migration rules…" },
  { key: "generating_plan", label: "Building Upgrade Plan", copy: "Building upgrade plan…" },
  { key: "scoring", label: "Calculating Confidence", copy: "Scoring readiness…" },
  { key: "analyzing_impact", label: "Building Upgrade Plan", copy: "Analyzing impact…" },
];

const SCAN_ALIASES: Record<string, string> = {
  pending: "queued",
  recovering: "recovering",
  classifying: "classifying",
  scanning_manifests: "manifests",
  parsing_ast: "ast",
  checking_versions: "versions",
  checking_vulnerabilities: "vulnerabilities",
  checking_licenses: "knowledge",
  scoring_health: "health",
  // Legacy scans that still emit analyzing_ai → treat as health/finalize
  analyzing_ai: "health",
  failed: "completed",
  cancelled: "completed",
};

const AI_ADVISOR_ALIASES: Record<string, string> = {
  pending: "queued",
  running: "preparing",
  analyzing_ai: "analyzing",
  failed: "completed",
  cancelled: "completed",
};

const SIM_ALIASES: Record<string, string> = {
  pending: "queued",
  collecting_sources: "preparing",
  learning_rules: "matching_rules",
  matching_rules: "matching_rules",
  filling_categories: "filling_categories",
  analyzing_impact: "filling_categories",
  generating_plan: "building_plan",
  scoring: "calculating_confidence",
  failed: "completed",
  cancelled: "completed",
};

export type TimelineStepState = "pending" | "running" | "completed" | "failed" | "locked";

export type TimelineStep = StageDef & {
  state: TimelineStepState;
};

function normalizeStage(
  stage: string | null | undefined,
  aliases: Record<string, string>,
  stages: StageDef[],
): string {
  if (!stage) return stages[0]?.key || "queued";
  const raw = stage.toLowerCase().replace(/\s+/g, "_");
  const mapped = aliases[raw] || raw;
  if (stages.some((s) => s.key === mapped)) return mapped;
  return stages[0]?.key || "queued";
}

/** Deduplicate stages that share labels after alias collapse (simulation). */
export function uniqueStages(stages: StageDef[]): StageDef[] {
  const seen = new Set<string>();
  const out: StageDef[] = [];
  for (const s of stages) {
    if (seen.has(s.key)) continue;
    // Skip legacy keys that are only aliases
    if (
      [
        "collecting_sources",
        "learning_rules",
        "generating_plan",
        "scoring",
        "analyzing_impact",
      ].includes(s.key)
    ) {
      continue;
    }
    seen.add(s.key);
    out.push(s);
  }
  return out;
}

export function buildTimeline(
  stages: StageDef[],
  currentStage: string | null | undefined,
  opts: {
    progress?: number;
    status?: string;
    aliases?: Record<string, string>;
    failed?: boolean;
    /** Stages that must never run — shown locked instead of completed/pending. */
    lockedStages?: string[];
    lockedCopy?: string;
  } = {},
): TimelineStep[] {
  const list = uniqueStages(stages);
  const aliases = opts.aliases || {};
  const locked = new Set(opts.lockedStages || []);
  const lockedCopy = opts.lockedCopy || "Available on Team+";
  const normalized = normalizeStage(currentStage, aliases, list);
  let idx = list.findIndex((s) => s.key === normalized);
  if (idx < 0) idx = 0;

  const done =
    opts.status === "completed" ||
    normalized === "completed" ||
    (opts.progress !== undefined && opts.progress >= 100);
  const failed = !!opts.failed || opts.status === "failed";
  const showNextCompleted =
    !done &&
    !failed &&
    opts.status === "running" &&
    opts.progress !== undefined &&
    opts.progress > 0 &&
    opts.progress < 100;

  return list.map((s, i) => {
    if (locked.has(s.key)) {
      return { ...s, state: "locked" as const, copy: lockedCopy };
    }
    if (failed && i === idx) return { ...s, state: "failed" as const };
    if (done || i < idx) return { ...s, state: "completed" as const };
    if (showNextCompleted && i === idx + 1) return { ...s, state: "completed" as const };
    if (i === idx) return { ...s, state: "running" as const };
    return { ...s, state: "pending" as const };
  });
}

export function scanTimeline(
  currentStage: string | null | undefined,
  progress: number,
  status: string,
  kind: "scan" | "sync" | "ai_advisor" = "scan",
) {
  if (kind === "ai_advisor") {
    return buildTimeline(AI_ADVISOR_STAGES, currentStage, {
      progress,
      status,
      aliases: AI_ADVISOR_ALIASES,
      failed: status === "failed",
    });
  }
  return buildTimeline(kind === "sync" ? SYNC_STAGES : SCAN_STAGES, currentStage, {
    progress,
    status,
    aliases: SCAN_ALIASES,
    failed: status === "failed",
  });
}

export function aiAdvisorTimeline(
  currentStage: string | null | undefined,
  progress: number,
  status: string,
) {
  return scanTimeline(currentStage, progress, status, "ai_advisor");
}

export function simulationTimeline(
  currentStage: string | null | undefined,
  progress: number,
  status: string,
  opts: { lockAiMigrationAssistant?: boolean } = {},
) {
  return buildTimeline(SIMULATION_STAGES, currentStage, {
    progress,
    status,
    aliases: SIM_ALIASES,
    failed: status === "failed",
    lockedStages: opts.lockAiMigrationAssistant
      ? ["ai_migration_assistant"]
      : undefined,
    lockedCopy: "Available on Team+",
  });
}

export function stageCopy(
  stages: StageDef[],
  currentStage: string | null | undefined,
  aliases: Record<string, string> = {},
): string {
  const list = uniqueStages(stages);
  const key = normalizeStage(currentStage, aliases, list);
  return list.find((s) => s.key === key)?.copy || "Working…";
}

export { SCAN_ALIASES, SIM_ALIASES, AI_ADVISOR_ALIASES };
