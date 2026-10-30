import type {
  BreakingAPI,
  DeprecatedAPI,
  MigrationFindingStatus,
  MigrationRule,
  SuggestedChange,
  UpgradeSimulation,
} from "@/types";
import { isStaleIntelligenceSimulation, resolveSuggestedChangeStatus } from "@/lib/upgrade-simulator";

const SECURITY_URL_HINTS = [
  "/security",
  "security.github.com",
  "/security/advisories",
  "osv.dev",
  "nvd.nist.gov",
  "cve.mitre.org",
  "snyk.io/vuln",
];

export type MigrationOverallStatus =
  | "no_changes"
  | "unknown"
  | "unresolved"
  | "breaking"
  | "deprecated"
  | "manual_review"
  | "docs_unavailable"
  | "in_progress";

export type ConfidenceBand = "high" | "medium" | "low";

export function confidenceBand(confidence: number): ConfidenceBand {
  const pct = confidence <= 1 ? confidence * 100 : confidence;
  if (pct >= 90) return "high";
  if (pct >= 70) return "medium";
  return "low";
}

export function confidenceLabel(confidence: number): string {
  const band = confidenceBand(confidence);
  if (band === "high") return "High";
  if (band === "medium") return "Medium";
  return "Low";
}

export function confidencePercent(confidence: number): number {
  if (confidence == null || Number.isNaN(confidence)) return 0;
  return Math.round(confidence <= 1 ? confidence * 100 : confidence);
}

export function isSecurityReference(url: string): boolean {
  const lower = url.toLowerCase();
  return SECURITY_URL_HINTS.some((h) => lower.includes(h));
}

export function migrationReferences(sim: UpgradeSimulation): string[] {
  const raw = [
    ...(sim.official_references || []),
    ...(sim.breaking_apis || []).map((b) => b.official_reference),
    ...(sim.deprecated_apis || []).map((d) => d.official_reference),
    ...(sim.suggested_changes || []).map((s) => s.official_reference),
    ...(sim.migration_rules || []).map((r) => r.official_reference),
  ].filter(Boolean) as string[];

  const unique: string[] = [];
  const seen = new Set<string>();
  for (const href of raw) {
    const key = href.trim();
    if (!key || seen.has(key) || isSecurityReference(key)) continue;
    seen.add(key);
    unique.push(key);
  }
  return unique;
}

export function classifyReference(url: string): string {
  const lower = url.toLowerCase();
  if (lower.includes("migration") || lower.includes("upgrade") || lower.includes("how-to")) {
    return "Official Migration Guide";
  }
  if (lower.includes("changelog") || lower.includes("changes")) return "Changelog";
  if (
    lower.includes("/releases/") ||
    (lower.includes("github.com") && lower.includes("/releases"))
  ) {
    return "GitHub Release";
  }
  if (lower.includes("release") || lower.includes("whatsnew") || lower.includes("what-s-new")) {
    return "Release Notes";
  }
  if (lower.includes("docs.") || lower.includes("/api") || lower.includes("readthedocs")) {
    return "API Documentation";
  }
  if (lower.includes("pypi.org")) return "PyPI";
  return "Documentation";
}

export function resolveFindingStatus(
  change: SuggestedChange,
): MigrationFindingStatus {
  return resolveSuggestedChangeStatus(change);
}

export function overallMigrationStatus(sim: UpgradeSimulation): MigrationOverallStatus {
  const inProgress = [
    "pending",
    "queued",
    "collecting_sources",
    "analyzing_impact",
    "generating_plan",
    "scoring",
    "preparing",
    "detecting_api",
    "matching_rules",
    "building_plan",
    "generating_suggestions",
    "calculating_confidence",
  ].includes(sim.status);
  if (inProgress) return "in_progress";

  const changes = sim.suggested_changes || [];
  const statuses = changes.map(resolveFindingStatus);
  const hasManual = statuses.includes("manual_review_required");
  const hasAuto = statuses.includes("automatic_migration");
  const hasUnknown = statuses.includes("unknown");
  const hasUnresolved = statuses.includes("unresolved");
  const breaking = sim.breaking_apis || [];
  const deprecated = sim.deprecated_apis || [];
  const refs = migrationReferences(sim);
  const rules = sim.migration_rules || [];
  const intel =
    sim.dynamic_intelligence ||
    (sim.collected_sources?.dynamic_intelligence as UpgradeSimulation["dynamic_intelligence"]);
  const hasIntelligence = !!(intel && intel.categories);

  if (hasManual) return "manual_review";
  if (breaking.length) return "breaking";
  if (deprecated.length) return "deprecated";
  if (hasAuto) return "breaking";
  if (hasUnresolved && hasIntelligence) return "unresolved";

  const usageCount =
    Number(sim.readiness_factors?.ast_usage_sites) ||
    Number(sim.readiness_factors?.semantic_index_sites) ||
    (sim.affected_files || []).reduce((n, f) => n + (f.usage_sites?.length || 0), 0) ||
    changes.length;

  // Fresh intelligence reports must not collapse to catalog-Unknown just because
  // no structured migration rules exist.
  if (hasIntelligence && !isStaleIntelligenceSimulation(sim)) {
    if (hasUnknown) return "unknown";
    if (hasUnresolved) return "unresolved";
    if (usageCount > 0) return "manual_review";
    return "unresolved";
  }

  // No deterministic knowledge → Unknown (never "No Changes Required")
  if (hasUnknown || (usageCount > 0 && rules.length === 0)) {
    return "unknown";
  }

  if (usageCount > 0 || sim.status === "completed") {
    if (!refs.length && !rules.length && !changes.length) {
      const sites = Number(sim.readiness_factors?.ast_usage_sites) || 0;
      if (sites === 0 && !(sim.affected_files || []).length) return "docs_unavailable";
    }
    // Only when positively verified (rules present, no actionable findings)
    if (rules.length > 0 || statuses.every((s) => s === "no_migration_required")) {
      return "no_changes";
    }
    return "unknown";
  }

  if (!refs.length) return "docs_unavailable";
  return "unknown";
}

export function migrationStatusLabel(status: MigrationOverallStatus): string {
  switch (status) {
    case "no_changes":
      return "No Changes Required";
    case "unknown":
      return "Unknown";
    case "unresolved":
      return "Unresolved";
    case "breaking":
      return "Breaking Changes Detected";
    case "deprecated":
      return "Deprecated APIs Found";
    case "manual_review":
      return "Manual Review Required";
    case "docs_unavailable":
      return "Documentation Unavailable";
    case "in_progress":
      return "Analyzing…";
  }
}

export type UsageAggregate = {
  symbol: string;
  count: number;
  files: Set<string>;
  kind?: string;
};

export function aggregateUsages(sim: UpgradeSimulation): UsageAggregate[] {
  const map = new Map<string, UsageAggregate>();

  for (const file of sim.affected_files || []) {
    for (const site of file.usage_sites || []) {
      const symbol = site.symbol || site.fully_qualified_name || "unknown";
      const key = symbol;
      const entry = map.get(key) || { symbol, count: 0, files: new Set<string>(), kind: site.usage_kind || undefined };
      entry.count += 1;
      entry.files.add(file.file_path);
      map.set(key, entry);
    }
    for (const api of file.affected_apis || []) {
      if (!map.has(api)) {
        map.set(api, { symbol: api, count: 1, files: new Set([file.file_path]) });
      }
    }
  }

  for (const change of sim.suggested_changes || []) {
    if (!change.symbol) continue;
    const entry =
      map.get(change.symbol) ||
      ({ symbol: change.symbol, count: 0, files: new Set<string>() } as UsageAggregate);
    if (entry.count === 0) entry.count = 1;
    entry.files.add(change.file_path);
    map.set(change.symbol, entry);
  }

  return [...map.values()].sort((a, b) => b.count - a.count);
}

export function buildAssistantSummary(sim: UpgradeSimulation) {
  const changes = sim.suggested_changes || [];
  const auto = changes.filter((c) => resolveFindingStatus(c) === "automatic_migration");
  const manual = changes.filter((c) => resolveFindingStatus(c) === "manual_review_required");
  const compatible = changes.filter((c) => resolveFindingStatus(c) === "no_migration_required");
  const unknown = changes.filter((c) => resolveFindingStatus(c) === "unknown");

  const usageSites =
    Number(sim.readiness_factors?.ast_usage_sites) ||
    Number(sim.readiness_factors?.semantic_index_sites) ||
    (sim.affected_files || []).reduce((n, f) => n + (f.usage_sites?.length || 1), 0) ||
    changes.length;

  const requireMigration = auto.length + manual.length;
  // Never invent "fully compatible" from Unknown — only positively verified no-change rows
  const fullyCompatible = compatible.length;

  const hours = sim.migration_time_hours;
  const minutes =
    hours != null ? Math.max(1, Math.round(Number(hours) * 60)) : requireMigration * 8;

  return {
    usageSites,
    requireMigration,
    fullyCompatible,
    unknownCount: unknown.length,
    autoFixes: auto.length,
    manualChanges: manual.length,
    estimatedMinutes: minutes,
    confidence: sim.confidence ?? 0,
    status: overallMigrationStatus(sim),
  };
}

export function highConfidencePatches(sim: UpgradeSimulation): SuggestedChange[] {
  return (sim.suggested_changes || []).filter((c) => {
    if (resolveFindingStatus(c) !== "automatic_migration") return false;
    return c.confidence >= 0.95 && !!c.suggested_code;
  });
}

export function buildUnifiedPatch(changes: SuggestedChange[]): string {
  const parts: string[] = [
    `# Migration patch generated by Dependency Intelligence`,
    `# ${changes.length} automatic change(s)`,
    "",
  ];
  for (const c of changes) {
    if (c.unified_diff) {
      parts.push(c.unified_diff);
      parts.push("");
      continue;
    }
    parts.push(`--- a/${c.file_path}`);
    parts.push(`+++ b/${c.file_path}`);
    if (c.line != null) parts.push(`@@ line ${c.line} @@`);
    for (const line of (c.current_code || "").split("\n")) {
      parts.push(`-${line}`);
    }
    for (const line of (c.suggested_code || "").split("\n")) {
      parts.push(`+${line}`);
    }
    parts.push("");
  }
  return parts.join("\n");
}

export function estimateFixMinutes(effort?: string | null, confidence?: number): number {
  const e = (effort || "").toLowerCase();
  if (e.includes("trivial") || e.includes("low")) return 5;
  if (e.includes("medium")) return 15;
  if (e.includes("high") || e.includes("very")) return 45;
  if (confidence != null && confidence >= 0.9) return 8;
  if (confidence != null && confidence >= 0.7) return 15;
  return 25;
}

export function filterAssistantItems(
  sim: UpgradeSimulation,
  query: string,
  filter: string,
): {
  changes: SuggestedChange[];
  rules: MigrationRule[];
  breaking: BreakingAPI[];
  deprecated: DeprecatedAPI[];
} {
  const q = query.trim().toLowerCase();
  const match = (...vals: Array<string | null | undefined>) => {
    if (!q) return true;
    return vals.some((v) => (v || "").toLowerCase().includes(q));
  };

  let changes = [...(sim.suggested_changes || [])];
  let rules = [...(sim.migration_rules || [])];
  let breaking = [...(sim.breaking_apis || [])];
  let deprecated = [...(sim.deprecated_apis || [])];

  if (filter === "automatic") {
    changes = changes.filter((c) => resolveFindingStatus(c) === "automatic_migration");
  } else if (filter === "manual") {
    changes = changes.filter((c) => resolveFindingStatus(c) === "manual_review_required");
  } else if (filter === "compatible") {
    changes = changes.filter((c) => resolveFindingStatus(c) === "no_migration_required");
  } else if (filter === "unknown") {
    changes = changes.filter((c) => resolveFindingStatus(c) === "unknown");
  } else if (filter === "breaking") {
    changes = [];
    rules = rules.filter((r) => r.severity === "high" || r.kind?.includes("breaking"));
    deprecated = [];
  } else if (filter === "deprecated") {
    changes = [];
    breaking = [];
    rules = rules.filter((r) => r.kind?.includes("deprecated") || r.severity === "medium");
  }

  changes = changes.filter((c) =>
    match(c.symbol, c.file_path, c.explanation, c.current_code, c.suggested_code, c.migration_status),
  );
  rules = rules.filter((r) =>
    match(r.symbol, r.description, r.kind, r.before, r.after, r.reason),
  );
  breaking = breaking.filter((b) =>
    match(b.symbol, b.fully_qualified_name, b.reason, b.replacement),
  );
  deprecated = deprecated.filter((d) =>
    match(d.symbol, d.fully_qualified_name, d.reason, d.replacement),
  );

  return { changes, rules, breaking, deprecated };
}
