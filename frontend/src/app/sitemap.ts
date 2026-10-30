import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_APP_URL || "https://dependencyintelligence.dev";
  const paths = [
    "",
    "/pricing",
    "/roadmap",
    "/changelog",
    "/feedback",
    "/contact",
    "/docs",
    "/blog",
    "/legal/privacy",
    "/legal/terms",
    "/legal/cookies",
  ];
  return paths.map((path) => ({
    url: `${base}${path}`,
    lastModified: new Date(),
    changeFrequency: path === "" ? "weekly" : "monthly",
    priority: path === "" ? 1 : 0.7,
  }));
}
