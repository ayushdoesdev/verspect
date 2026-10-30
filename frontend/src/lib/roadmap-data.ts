export type RoadmapItem = {
  id: string;
  title: string;
  description?: string;
};

export const ROADMAP: Record<"planned" | "in_progress" | "released", RoadmapItem[]> = {
  planned: [
    { id: "gitlab", title: "GitLab Integration", description: "Import and sync GitLab repositories" },
    { id: "bitbucket", title: "Bitbucket Integration" },
    { id: "vscode", title: "VS Code Extension" },
  ],
  in_progress: [
    {
      id: "private-beta",
      title: "Private Beta Hardening",
      description: "Reliability, recovery, and early-access experience",
    },
    {
      id: "ai-advisor",
      title: "AI Upgrade Advisor polish",
      description: "Faster insights and clearer recommendations",
    },
    { id: "cli", title: "CLI", description: "Scan and report from the terminal" },
  ],
  released: [
    { id: "github", title: "GitHub Integration" },
    { id: "python", title: "Python Dependency Intelligence" },
    {
      id: "nodejs",
      title: "Node.js / TypeScript Support",
      description: "npm, yarn, and pnpm manifests with import usage",
    },
    {
      id: "go",
      title: "Go Support",
      description: "go.mod / go.sum dependency intelligence",
    },
    {
      id: "java",
      title: "Java Support",
      description: "Maven and Gradle dependency intelligence",
    },
    {
      id: "rust",
      title: "Rust Support",
      description: "Cargo.toml / Cargo.lock analysis",
    },
    {
      id: "php",
      title: "PHP Support",
      description: "Composer dependency intelligence",
    },
    {
      id: "ruby",
      title: "Ruby Support",
      description: "Bundler / Gemfile analysis",
    },
    { id: "github-pr", title: "Opt-in GitHub migration PRs", description: "Create a PR only after explicit confirmation" },
    { id: "migration", title: "AI Migration Assistant" },
    { id: "security", title: "Vulnerability & License Scanning" },
    { id: "feedback", title: "Feedback Center" },
  ],
};
