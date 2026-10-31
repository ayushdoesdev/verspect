export function getSiteOrigin(): string {
  const configuredOrigin = process.env.NEXT_PUBLIC_SITE_URL;
  if (configuredOrigin) return new URL(configuredOrigin).origin;

  // Use the public custom domain for production canonical and social metadata URLs.
  if (process.env.VERCEL_ENV === "production") {
    return "https://verspect.akstechies.com";
  }

  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://localhost:3000";
}
