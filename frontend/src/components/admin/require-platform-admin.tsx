"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { AdminShell } from "@/components/layout/admin-shell";
import { ErrorState } from "@/components/loading";

/** Gate admin console pages: must be authenticated platform admin. */
export function RequirePlatformAdmin({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "loading" || auth.isTransitioning) return;
    if (auth.status === "unauthenticated") {
      router.replace("/admin/login");
    }
  }, [auth.status, auth.isTransitioning, router]);

  if (auth.status === "loading" || auth.isTransitioning) {
    return <AuthLoadingScreen message="Loading platform…" />;
  }

  if (!auth.isAuthenticated) {
    return <AuthLoadingScreen message="Redirecting to admin sign in…" />;
  }

  if (!auth.user?.is_admin) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-md">
          <ErrorState
            title="Access denied"
            description="This console is restricted to platform administrators."
          />
          <button
            type="button"
            className="mt-4 w-full rounded-md border border-border px-3 py-2 text-sm"
            onClick={() => {
              auth.logout();
              router.replace("/admin/login");
            }}
          >
            Sign in as platform admin
          </button>
        </div>
      </div>
    );
  }

  return <AdminShell>{children}</AdminShell>;
}
