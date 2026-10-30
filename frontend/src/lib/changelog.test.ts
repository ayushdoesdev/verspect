import { describe, expect, it } from "vitest";
import { CHANGELOG } from "@/lib/changelog";
import { ROADMAP } from "@/lib/roadmap-data";
import { PRICING_COPY } from "@/lib/evaluation-copy";
import { BLOG_POSTS, getBlogPost } from "@/lib/blog";

describe("private beta content", () => {
  it("changelog is newest-first with version and changes", () => {
    expect(CHANGELOG.length).toBeGreaterThan(0);
    expect(CHANGELOG[0].version).toBeTruthy();
    expect(CHANGELOG[0].changes.length).toBeGreaterThan(0);
  });

  it("roadmap has planned, in progress, and released columns", () => {
    expect(ROADMAP.planned.length).toBeGreaterThan(0);
    expect(ROADMAP.in_progress.length).toBeGreaterThan(0);
    expect(ROADMAP.released.length).toBeGreaterThan(0);
  });

  it("evaluation notice explains evaluation intent", () => {
    expect(PRICING_COPY.name).toBe("Evaluation Plan");
    expect(PRICING_COPY.tagline.toLowerCase()).toContain("evaluating");
    expect(PRICING_COPY.aiNote.toLowerCase()).toContain("paid");
    expect(PRICING_COPY.notice.toLowerCase()).toContain("early version");
  });

  it("blog posts have bodies and unique slugs", () => {
    expect(BLOG_POSTS.length).toBeGreaterThan(0);
    const slugs = BLOG_POSTS.map((p) => p.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const post of BLOG_POSTS) {
      expect(post.body.length).toBeGreaterThan(0);
      expect(getBlogPost(post.slug)?.title).toBe(post.title);
    }
  });
});
