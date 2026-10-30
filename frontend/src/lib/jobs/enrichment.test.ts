import { describe, expect, it } from "vitest";
import {
  ENRICHMENT_ROTATION,
  enrichmentCountLabel,
  enrichmentPhaseCopy,
  isEnrichmentStage,
  parseEnrichment,
} from "./enrichment";

describe("parseEnrichment", () => {
  it("reads enrichment from extra_metadata", () => {
    expect(
      parseEnrichment({
        enrichment: { package: "pydantic", index: 7, total: 14, phase: "health" },
      }),
    ).toEqual({ package: "pydantic", index: 7, total: 14, phase: "health" });
  });

  it("falls back to summary", () => {
    expect(
      parseEnrichment(null, {
        enrichment: { package: "fastapi", index: 1, total: 14, phase: "versions" },
      }),
    ).toMatchObject({ package: "fastapi" });
  });
});

describe("enrichment helpers", () => {
  it("maps phases to deterministic copy", () => {
    expect(enrichmentPhaseCopy("versions")).toBe("Checking latest version");
    expect(enrichmentPhaseCopy("metadata")).toBe("Fetching package metadata");
    expect(enrichmentPhaseCopy("vulnerabilities")).toBe("Checking security advisories");
    expect(enrichmentPhaseCopy("health")).toBe("Calculating health score");
    expect(enrichmentPhaseCopy("alternatives")).toBe("Finding alternative libraries");
    expect(enrichmentPhaseCopy("persisting")).toBe("Saving dependency intelligence");
    expect(enrichmentPhaseCopy("complete")).toBe("Dependency Intelligence Complete");
  });

  it("never uses AI or recommendations wording in rotation", () => {
    const blob = ENRICHMENT_ROTATION.join(" ").toLowerCase();
    expect(blob).not.toMatch(/ai|recommend/);
    expect(blob).not.toContain("building dependency intelligence");
  });

  it("formats package counts", () => {
    expect(enrichmentCountLabel({ index: 8, total: 14 })).toBe("8 of 14 packages");
    expect(enrichmentCountLabel({})).toBeNull();
  });

  it("detects enrichment stages", () => {
    expect(isEnrichmentStage("knowledge")).toBe(true);
    expect(isEnrichmentStage("checking_licenses")).toBe(true);
    expect(isEnrichmentStage("cloning")).toBe(false);
  });
});
