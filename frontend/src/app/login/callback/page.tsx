"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";

function CallbackInner() {
  const params = useSearchParams();
  const auth = useAuth();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const completeSignIn = useRef(auth.completeSignIn);
  completeSignIn.current = auth.completeSignIn;

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    let cancelled = false;

    async function complete() {
      // Legacy JWT-in-URL callbacks are rejected — tokens must never appear in the query string.
      if (params.get("access_token") || params.get("refresh_token")) {
        if (!cancelled) {
          setError("Invalid sign-in link. Please sign in again.");
        }
        return;
      }

      const code = params.get("code");
      if (!code) {
        if (!cancelled) setError("Missing sign-in code. Please try again.");
        return;
      }
      try {
        const tokens = await api.exchangeOAuthCode(code);
        // Drop the one-time code from the address bar before storing session tokens.
        if (typeof window !== "undefined") {
          window.history.replaceState({}, "", "/login/callback");
        }
        await completeSignIn.current({
          access: tokens.access_token,
          refresh: tokens.refresh_token,
          user: tokens.user,
        });
      } catch {
        if (!cancelled) setError("Unable to complete sign-in");
      }
    }

    void complete();
    return () => {
      cancelled = true;
    };
  }, [params]);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#070b12] px-4 text-center">
        <p className="text-sm text-destructive">{error}</p>
        <a href="/login" className="text-sm text-teal-300 hover:underline">
          Back to sign in
        </a>
      </div>
    );
  }

  return <AuthLoadingScreen message={auth.loadingMessage || "Completing sign-in…"} />;
}

export default function LoginCallbackPage() {
  return (
    <Suspense fallback={<AuthLoadingScreen message="Completing sign-in…" />}>
      <CallbackInner />
    </Suspense>
  );
}
