import type { NextConfig } from "next";

/**
 * Dev and production must not share a distDir.
 *
 * Original runtime 404s: `next build` wrote hashed chunks into `.next` while
 * `next dev` still emitted unhashed URLs (`/_next/static/chunks/main-app.js`).
 * A later in-container `next build` also polluted `.next-dev` because Next
 * worker processes re-evaluate this file without `dev` in argv.
 *
 * NEXT_DIST_DIR is inherited by those workers; argv is not. npm scripts and
 * Compose/Dockerfiles set it explicitly.
 */
const distDir =
  process.env.NEXT_DIST_DIR ||
  (process.argv.includes("dev") ? ".next-dev" : ".next");

const isDevDist = distDir === ".next-dev";

const nextConfig: NextConfig = {
  distDir,
  // Standalone is for production images. During `next dev` it leaves
  // prerender manifests that do not match unhashed dev chunk URLs.
  ...(!isDevDist ? { output: "standalone" as const } : {}),
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
      { protocol: "https", hostname: "github.com" },
    ],
  },
};

export default nextConfig;
