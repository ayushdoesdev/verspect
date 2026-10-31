import type { Metadata, Viewport } from "next";
import { getSiteOrigin } from "@/lib/site-origin";
import "./globals.css";

const siteOrigin = new URL(getSiteOrigin());

export const metadata: Metadata = {
  metadataBase: siteOrigin,
  title: "Verspect — Dependency intelligence for GitHub repositories",
  description:
    "Understand dependency relationships, security and license findings, package health, and upgrade impact with self-hosted, evidence-led analysis.",
  applicationName: "Verspect",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    title: "Verspect — Dependency intelligence for GitHub repositories",
    description:
      "Know your dependencies. Understand your risks. Upgrade with confidence.",
    siteName: "Verspect",
  },
  twitter: {
    card: "summary_large_image",
    title: "Verspect — Dependency intelligence for GitHub repositories",
    description:
      "Know your dependencies. Understand your risks. Upgrade with confidence.",
  },
  robots: { index: true, follow: true },
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#070b12",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Global App Router stylesheet uses the same public type family as the reference site. */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700&family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
