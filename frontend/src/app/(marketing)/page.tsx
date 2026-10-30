import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verspect — Know every upgrade before you ship it",
  description:
    "Scan repositories, simulate breaking changes, and generate exact migration patches. Dependency intelligence for engineering teams.",
  keywords: [
    "Verspect",
    "Python",
    "JavaScript",
    "TypeScript",
    "Go",
    "dependency upgrade",
    "dependency upgrade",
    "CVE scanning",
    "migration planning",
    "AST analysis",
    "upgrade simulator",
  ],
  openGraph: {
    title: "Verspect",
    description: "Know every upgrade before you ship it.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Verspect",
    description: "Know every upgrade before you ship it.",
  },
};

export { default } from "./page-client";
