import { describe, expect, it } from "vitest";
import {
  jobStatusLabel,
  mapScanJobStatus,
  mapSimulationJobStatus,
  parseBackendTime,
} from "./status";
import {
  scanTimeline,
  simulationTimeline,
  uniqueStages,
  SIMULATION_STAGES,
} from "./stages";

describe("mapScanJobStatus", () => {
  it("maps queue states to pending", () => {
    expect(mapScanJobStatus("pending")).toBe("pending");
    expect(mapScanJobStatus("queued")).toBe("pending");
  });

  it("maps worker stages to running", () => {
    expect(mapScanJobStatus("running")).toBe("running");
    expect(mapScanJobStatus("cloning")).toBe("running");
    expect(mapScanJobStatus("parsing_ast")).toBe("running");
    expect(mapScanJobStatus("analyzing_ai")).toBe("running");
  });

  it("maps terminal states", () => {
    expect(mapScanJobStatus("completed")).toBe("completed");
    expect(mapScanJobStatus("failed")).toBe("failed");
  });

  it("keeps cancellation distinct from failure", () => {
    expect(mapScanJobStatus("cancelled")).toBe("cancelled");
  });
});

describe("mapSimulationJobStatus", () => {
  it("maps pending and running", () => {
    expect(mapSimulationJobStatus("queued")).toBe("pending");
    expect(mapSimulationJobStatus("matching_rules")).toBe("running");
    expect(mapSimulationJobStatus("completed")).toBe("completed");
  });

  it("keeps cancellation distinct from failure", () => {
    expect(mapSimulationJobStatus("cancelled")).toBe("cancelled");
  });
});

describe("jobStatusLabel", () => {
  it("prioritises worker outage over job state", () => {
    expect(jobStatusLabel({ status: "pending", workerOffline: true })).toBe("Worker Offline");
  });

  it("explains a long wait as stalled", () => {
    expect(jobStatusLabel({ status: "pending", stalled: true })).toBe("Stalled");
  });

  it("distinguishes queue congestion from a plain wait", () => {
    expect(jobStatusLabel({ status: "pending", queueBlocked: true })).toBe("Queue Blocked");
    expect(jobStatusLabel({ status: "pending" })).toBe("Waiting for worker");
  });

  it("reports preparation before the first real stage", () => {
    expect(
      jobStatusLabel({ status: "running", currentStage: "queued", progress: 2 }),
    ).toBe("Preparing repository");
  });

  it("reports scanning and finishing while running", () => {
    expect(jobStatusLabel({ status: "running", currentStage: "ast", progress: 55 })).toBe(
      "Scanning",
    );
    expect(jobStatusLabel({ status: "running", currentStage: "health", progress: 97 })).toBe(
      "Finishing",
    );
  });

  it("labels terminal states", () => {
    expect(jobStatusLabel({ status: "completed" })).toBe("Completed");
    expect(jobStatusLabel({ status: "failed" })).toBe("Failed");
    expect(jobStatusLabel({ status: "cancelled" })).toBe("Cancelled");
  });
});

describe("parseBackendTime", () => {
  it("returns null for missing started_at", () => {
    expect(parseBackendTime(null)).toBeNull();
    expect(parseBackendTime(undefined)).toBeNull();
  });

  it("parses ISO timestamps", () => {
    const ms = parseBackendTime("2026-08-01T10:00:00.000Z");
    expect(ms).toBe(Date.parse("2026-08-01T10:00:00.000Z"));
  });
});

describe("scanTimeline", () => {
  it("marks prior stages completed and current running", () => {
    const steps = scanTimeline("ast", 32, "running");
    const ast = steps.find((s) => s.key === "ast");
    const manifests = steps.find((s) => s.key === "manifests");
    const vulns = steps.find((s) => s.key === "vulnerabilities");
    expect(manifests?.state).toBe("completed");
    expect(ast?.state).toBe("running");
    expect(vulns?.state).toBe("pending");
  });

  it("completes all steps at 100%", () => {
    const steps = scanTimeline("completed", 100, "completed");
    expect(steps.every((s) => s.state === "completed")).toBe(true);
  });
});

describe("simulationTimeline", () => {
  it("maps legacy scoring stage", () => {
    const steps = simulationTimeline("scoring", 90, "scoring");
    const conf = steps.find((s) => s.key === "calculating_confidence");
    expect(conf?.state).toBe("running");
  });

  it("includes filling_categories in the unique timeline", () => {
    const keys = uniqueStages(SIMULATION_STAGES).map((s) => s.key);
    expect(keys).toContain("filling_categories");
  });

  it("maps filling_categories as running", () => {
    expect(mapSimulationJobStatus("filling_categories")).toBe("running");
  });

  it("locks AI Migration Assistant when plan lacks Team entitlement", () => {
    const steps = simulationTimeline("calculating_confidence", 90, "running", {
      lockAiMigrationAssistant: true,
    });
    const assistant = steps.find((s) => s.key === "ai_migration_assistant");
    expect(assistant?.state).toBe("locked");
    expect(assistant?.copy).toMatch(/Team/i);
    // Must not look completed just because later stages are running
    expect(assistant?.state).not.toBe("completed");
  });
});
