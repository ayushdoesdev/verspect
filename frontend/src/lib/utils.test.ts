import { describe, expect, it } from "vitest";
import { cn, formatNumber, formatScore, statusBadge } from "@/lib/utils";

describe("utils", () => {
  it("merges class names", () => {
    expect(cn("px-2", "px-4")).toContain("px-4");
  });

  it("formats finite numbers compactly and handles invalid values", () => {
    expect(formatNumber(1200)).toBe("1.2K");
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(-1200)).toBe("-1.2K");
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
    expect(formatNumber(Number.POSITIVE_INFINITY)).toBe("—");
    expect(formatNumber(Number.NEGATIVE_INFINITY)).toBe("—");
  });

  it("formats scores", () => {
    expect(formatScore(87.4)).toBe("87");
    expect(formatScore(null)).toBe("—");
  });

  it("maps status badges", () => {
    expect(statusBadge("vulnerable")).toContain("destructive");
    expect(statusBadge("up_to_date")).toContain("success");
  });
});
