export type BlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  body: string[];
};

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: "stop-guessing-upgrades",
    title: "Stop guessing dependency upgrades",
    excerpt: "Why usage-aware migration intelligence beats changelog skimming.",
    date: "2026-08-01",
    body: [
      "Verspect starts from the repository you actually ship. Manifests and lockfiles build the inventory. Static analysis records where packages are imported or called. Upgrade impact then matches those sites against deterministic rules when we have them.",
      "A major version is not treated as breaking on its own. If we cannot prove a removed or changed API from a catalog or from your files, the finding is unresolved — not invented.",
      "Python currently has the deepest AST and migration catalogs. JavaScript, TypeScript, Go, Java, Rust, PHP, and Ruby get inventory, import-level usage, OSV, licenses, and health. That split is intentional.",
    ],
  },
  {
    slug: "security-vs-migration-pipelines",
    title: "Security intelligence is not migration documentation",
    excerpt: "How we separate advisories from upgrade guides.",
    date: "2026-08-01",
    body: [
      "OSV queries use ecosystem-correct package names (Maven keeps group:artifact). Matches include severity, ranges, and fixed versions when OSV provides them. Query failures do not create fake CVEs.",
      "Migration guidance is a different pipeline: catalog rules, optional AI over fenced release notes, and patches that must validate before we offer a GitHub pull request.",
      "You confirm before any PR is opened. Verspect will not push migration branches unattended.",
    ],
  },
];

export function getBlogPost(slug: string): BlogPost | undefined {
  return BLOG_POSTS.find((post) => post.slug === slug);
}
