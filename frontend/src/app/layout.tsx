import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Verspect",
    template: "%s · Verspect",
  },
  description:
    "Scan repositories, simulate breaking changes, and generate exact migration patches. Dependency intelligence for engineering teams.",
  keywords: [
    "Verspect",
    "Python",
    "JavaScript",
    "TypeScript",
    "Go",
    "Java",
    "Rust",
    "PHP",
    "Ruby",
    "dependency scanning",
    "dependency scanning",
    "CVE",
    "upgrade simulator",
    "migration planning",
    "SaaS",
  ],
  openGraph: {
    title: "Verspect",
    description: "Know every upgrade before you ship it.",
    siteName: "Verspect",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Verspect",
    description: "Know every upgrade before you ship it.",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Verspect",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Web",
    description:
      "Dependency intelligence for upgrades, security, and migrations across Python, JavaScript, TypeScript, Go, Java, Rust, PHP, and Ruby.",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
  };

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* Marketing webfonts for the public site; App Router has no _document. */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
