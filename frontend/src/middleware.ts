import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED = [
  "/dashboard",
  "/repositories",
  "/dependencies",
  "/settings",
  "/search",
  "/billing",
  "/team",
  "/usage",
  "/onboarding",
  "/upgrade-simulator",
  "/migration-assistant",
  "/security",
  "/admin",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const needsAuth = PROTECTED.some((p) => pathname === p || pathname.startsWith(p + "/"));
  if (!needsAuth) return NextResponse.next();

  // Tokens live in localStorage (SPA). Middleware cannot read them reliably.
  // Keep a soft gate via cookie if present; otherwise allow client-side redirect.
  const token = request.cookies.get("access_token")?.value;
  if (!token) {
    // Allow through — pages already redirect on 401 / missing me query
    return NextResponse.next();
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/repositories/:path*",
    "/dependencies/:path*",
    "/settings/:path*",
    "/billing/:path*",
    "/team/:path*",
    "/usage/:path*",
    "/onboarding/:path*",
    "/search/:path*",
    "/upgrade-simulator/:path*",
    "/migration-assistant/:path*",
    "/security/:path*",
    "/admin/:path*",
  ],
};
