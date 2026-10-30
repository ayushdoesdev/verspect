import { describe, expect, it } from "vitest";
import {
  getAssistantAvailabilityMessage,
  getSimulationLifecycleState,
  resolveActiveSimulationId,
  formatImpactLimitations,
  UPGRADE_ANALYSIS_SECTIONS,
  isLegacyCatalogUnknown,
  isStaleIntelligenceSimulation,
  resolveSuggestedChangeStatus,
} from "@/lib/upgrade-simulator";
import { overallMigrationStatus } from "@/lib/migration-assistant";
import type { SuggestedChange, UpgradeSimulation } from "@/types";

describe("upgrade simulator status helpers", () => {
  const IN_PROGRESS = new Set([
    "pending",
    "queued",
    "collecting_sources",
    "analyzing_impact",
    "generating_plan",
    "scoring",
  ]);

  it("lists every Upgrade Simulator analysis section", () => {
    expect([...UPGRADE_ANALYSIS_SECTIONS]).toEqual([
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
    ]);
  });

  it("treats analyzing stages as in progress", () => {
    expect(IN_PROGRESS.has("analyzing_impact")).toBe(true);
    expect(IN_PROGRESS.has("completed")).toBe(false);
    expect(IN_PROGRESS.has("failed")).toBe(false);
  });

  it("formats confidence percent", () => {
    const confidence = 0.72;
    expect(`${Math.round(confidence * 100)}%`).toBe("72%");
  });

  it("returns a Team upgrade prompt when the AI assistant is locked", () => {
    const message = getAssistantAvailabilityMessage({
      simCompleted: true,
      migrationLocked: true,
      canMigration: false,
    });

    expect(message?.kind).toBe("locked");
    expect(message?.title).toContain("Team");
    expect(message?.detail).toContain("Deterministic analysis");
  });

  it("explains when deterministic analysis completed without AI patch generation", () => {
    const message = getAssistantAvailabilityMessage({
      simCompleted: true,
      migrationLocked: false,
      canMigration: false,
    });

    expect(message?.kind).toBe("unavailable");
    expect(message?.detail).toContain("AI Migration Assistant");
    expect(message?.detail).toContain("patches");
  });

  it("marks stalled simulations as timed out", () => {
    const state = getSimulationLifecycleState({
      status: "running",
      startedAt: Date.now() - 11 * 60 * 1000,
      progress: 12,
      now: Date.now(),
    });

    expect(state.state).toBe("timed_out");
    expect(state.title).toContain("timed out");
  });

  it("marks cancelled runs as cancelled", () => {
    const state = getSimulationLifecycleState({
      status: "cancelled",
    });

    expect(state.state).toBe("cancelled");
    expect(state.actionLabel).toContain("Retry");
  });

  it("keeps an existing active simulation id instead of overriding it", () => {
    const resolved = resolveActiveSimulationId({
      activeId: "existing-sim",
      storedId: "stored-sim",
      simulations: [{ id: "first-sim" }],
    });

    expect(resolved).toBe("existing-sim");
  });

  it("drops blank analysis limitations", () => {
    expect(formatImpactLimitations(["  No catalog  ", "", "Unresolved APIs"])).toEqual([
      "No catalog",
      "Unresolved APIs",
    ]);
  });
});

function suggested(partial: Partial<SuggestedChange>): SuggestedChange {
  return {
    file_path: "src/Body.js",
    line: 3,
    symbol: "@mui/x-data-grid",
    current_code: "import { DataGrid } from '@mui/x-data-grid'",
    explanation: "",
    confidence: 0.3,
    automatic: false,
    ...partial,
  };
}

describe("upgrade simulator intelligence rendering contract", () => {
  it("does not treat an AI-assisted merged finding as catalog Unknown", () => {
    const change = suggested({
      explanation: "AI-assisted analysis — potentially breaking. Review DataGrid usage.",
      status_title: "AI-assisted analysis — potentially breaking",
      status_detail: "Documented typing changes overlap indexed usage.",
      migration_status: "manual_review_required",
      analysis_source: "deterministic+ai",
      confidence: 0.68,
    });
    expect(isLegacyCatalogUnknown(change)).toBe(false);
    expect(resolveSuggestedChangeStatus(change)).toBe("manual_review_required");
  });

  it("does not treat unmatched-usage No changes required as a clean upgrade", () => {
    const change = suggested({
      explanation:
        "No changes required — deterministic migration rules exist for this range and none match this usage.",
      status_title: "No changes required",
      migration_status: "no_migration_required",
    });
    expect(resolveSuggestedChangeStatus(change)).toBe("unresolved");
  });

  it("classifies an AI timeout finding as unresolved, not catalog Unknown", () => {
    const change = suggested({
      explanation:
        "AI-assisted analysis timed out before a structured result was ready. Deterministic evidence is preserved.",
      status_title: "AI-assisted analysis timed out",
      migration_status: "unresolved",
      analysis_source: "deterministic",
    });
    expect(isLegacyCatalogUnknown(change)).toBe(false);
    expect(resolveSuggestedChangeStatus(change)).toBe("unresolved");
  });

  it("does not classify genuine unresolved copy as catalog Unknown", () => {
    const change = suggested({
      explanation: "Unresolved — insufficient evidence after deterministic and AI analysis.",
      status_title: "Unresolved",
      migration_status: "unresolved",
      analysis_source: "deterministic+ai",
    });
    expect(isLegacyCatalogUnknown(change)).toBe(false);
    expect(resolveSuggestedChangeStatus(change)).toBe("unresolved");
  });

  it("still recognizes a legacy catalog-Unknown finding", () => {
    const change = suggested({
      explanation:
        "Unknown — no structured migration rules are available for this library/version range. Insufficient deterministic knowledge.",
      status_title: "Unknown",
      migration_status: "unknown",
      unknown: true,
    });
    expect(isLegacyCatalogUnknown(change)).toBe(true);
    expect(resolveSuggestedChangeStatus(change)).toBe("unknown");
  });

  it("renders a fresh no-catalog intelligence report instead of Unknown", () => {
    const sim = {
      status: "completed",
      suggested_changes: [
        suggested({
          explanation: "AI-assisted analysis — potentially breaking.",
          status_title: "AI-assisted analysis — potentially breaking",
          migration_status: "manual_review_required",
          analysis_source: "ai",
          confidence: 0.62,
        }),
      ],
      migration_rules: [],
      affected_files: [{ file_path: "src/Body.js", affected_apis: ["DataGrid"], reason: "import", confidence: 0.7 }],
      readiness_factors: { ast_usage_sites: 1 },
      dynamic_intelligence: {
        categories: { breaking_changes: { completeness: "partial" } },
        analysis_method: "ai",
        ai_invoked: true,
      },
      collected_sources: { intelligence_schema_version: 2 },
    } as unknown as UpgradeSimulation;
    expect(isStaleIntelligenceSimulation(sim)).toBe(false);
    expect(overallMigrationStatus(sim)).not.toBe("unknown");
    expect(resolveSuggestedChangeStatus(sim.suggested_changes![0])).not.toBe("unknown");
  });

  it("keeps genuine unresolved after deterministic and AI analysis", () => {
    const sim = {
      status: "completed",
      suggested_changes: [
        suggested({
          explanation: "Unresolved — insufficient evidence after deterministic and AI analysis.",
          status_title: "Unresolved",
          migration_status: "unresolved",
          analysis_source: "deterministic+ai",
        }),
      ],
      migration_rules: [],
      dynamic_intelligence: { categories: { breaking_changes: { completeness: "empty" } }, analysis_method: "ai" },
      collected_sources: { intelligence_schema_version: 2 },
    } as unknown as UpgradeSimulation;
    expect(overallMigrationStatus(sim)).toBe("unresolved");
  });

  it("marks pre-intelligence completed simulations as stale", () => {
    const sim = {
      status: "completed",
      suggested_changes: [
        suggested({
          explanation: "Unknown — insufficient deterministic knowledge.",
          migration_status: "unknown",
          unknown: true,
        }),
      ],
      collected_sources: {},
    } as unknown as UpgradeSimulation;
    expect(isStaleIntelligenceSimulation(sim)).toBe(true);
    expect(overallMigrationStatus(sim)).toBe("unknown");
  });
});
