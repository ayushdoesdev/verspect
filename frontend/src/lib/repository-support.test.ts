import { describe, expect, it } from "vitest";
import {
  hasPythonUpgradeCatalog,
  isAnalyzable,
  isFullySupported,
  isUnsupported,
  supportStatusLabel,
} from "./repository-support";

describe("repository support status", () => {
  it("treats javascript supported as analyzable, not planned", () => {
    const repo = { support_status: "supported", support_label: "Supported" };
    expect(supportStatusLabel(repo)).toBe("Supported");
    expect(isAnalyzable(repo)).toBe(true);
    expect(isFullySupported(repo)).toBe(false);
    expect(isUnsupported(repo)).toBe(false);
  });

  it("keeps python fully supported", () => {
    const repo = { support_status: "fully_supported" };
    expect(supportStatusLabel(repo)).toBe("Fully Supported");
    expect(isAnalyzable(repo)).toBe(true);
    expect(isFullySupported(repo)).toBe(true);
    expect(isUnsupported(repo)).toBe(false);
    expect(hasPythonUpgradeCatalog({ detected_language_id: "python" })).toBe(true);
  });

  it("maps coming_soon to Planned only when no analyzer exists", () => {
    const repo = { support_status: "coming_soon", support_label: "Coming Soon" };
    expect(supportStatusLabel(repo)).toBe("Planned");
    expect(isAnalyzable(repo)).toBe(false);
    expect(isUnsupported(repo)).toBe(true);
  });

  it("does not treat javascript as python-depth upgrade catalog", () => {
    expect(hasPythonUpgradeCatalog({ detected_language_id: "javascript" })).toBe(false);
  });
});
