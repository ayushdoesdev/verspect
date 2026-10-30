export type ChangelogEntry = {
  version: string;
  date: string;
  changes: string[];
};

/** Newest first. */
export const CHANGELOG: ChangelogEntry[] = [
  {
    version: "1.1.0",
    date: "2026-08-26",
    changes: [
      "Language scanners for JavaScript/TypeScript, Go, Java, Rust, PHP, and Ruby",
      "Opt-in GitHub pull requests after migration review",
      "Health scores omit unobserved signals instead of filling defaults",
      "Maven OSV lookups keep group:artifact coordinates",
    ],
  },
  {
    version: "1.0.0",
    date: "2026-08-01",
    changes: [
      "Private Beta launch of Verspect Dependency Intelligence",
      "Repository scan, sync, and dependency health scoring",
      "Upgrade Simulator and AI Upgrade Advisor",
      "AI Migration Assistant (Team+)",
      "Feedback Center and platform admin dashboard",
    ],
  },
  {
    version: "0.9.0",
    date: "2026-07-15",
    changes: [
      "Evaluation plan and billing entitlements",
      "Organization invites and team roles",
      "Worker recovery for interrupted repository scans",
    ],
  },
];
