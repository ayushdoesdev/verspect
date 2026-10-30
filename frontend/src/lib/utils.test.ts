import { describe, expect, it } from "vitest";
import { cn, formatScore, statusBadge } from "@/lib/utils";

describe("utils", () => {
  it("merges class names", () => {
    expect(cn("px-2", "px-4")).toContain("px-4");
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
