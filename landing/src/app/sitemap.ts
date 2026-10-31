import type { MetadataRoute } from "next";
import { getSiteOrigin } from "@/lib/site-origin";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: getSiteOrigin(),
      lastModified: new Date("2026-10-31"),
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}
