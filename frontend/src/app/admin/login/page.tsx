"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shield } from "lucide-react";
import { api, setTokens } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";

/**
 * Separate platform-admin sign-in UI.
 * Uses the same auth API; rejects non-admin accounts after login.
 */
export default function AdminLoginPage() {
  const auth = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("admin@verspect.dev");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.isTransitioning) return;
    if (auth.user?.is_admin) {
      router.replace("/admin");
    }
  }, [auth.status, auth.isTransitioning, auth.user, router]);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const tokens = await api.login({ email, password, remember_me: true });
      if (!tokens.access_token || !tokens.refresh_token) {
        throw new Error("Login response missing tokens");
      }

      setTokens(tokens.access_token, tokens.refresh_token, { silent: true });
      const user = tokens.user || (await api.me());

      if (!user?.is_admin) {
        auth.logout();
        setError("This account is not a platform administrator.");
        setLoading(false);
        return;
      }

      await auth.establishSession(tokens.access_token, tokens.refresh_token, user);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  if (auth.status === "loading" || auth.isTransitioning) {
    return null;
  }

  if (auth.isAuthenticated && auth.user?.is_admin) {
    return null;
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#070b12] px-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(61,214,198,0.1),transparent_50%)]" />
      <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.04] p-8 backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-400/15 text-teal-300">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <div className="mb-1">
              <PrivateBetaBadge variant="marketing" />
            </div>
            <h1 className="text-lg font-semibold text-white">Platform Admin</h1>
            <p className="text-sm text-slate-400">Sign in to the Verspect control plane</p>
          </div>
        </div>

        {auth.isAuthenticated && !auth.user?.is_admin ? (
          <div className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            You are signed in as a customer account. Sign out and use a platform admin
            credential.
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-3 w-full"
              onClick={() => auth.logout()}
            >
              Sign out customer session
            </Button>
          </div>
        ) : null}

        {error ? (
          <div className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <form className="space-y-3" onSubmit={login}>
          <Input
            type="email"
            required
            placeholder="Admin email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="bg-white/5"
            autoComplete="username"
          />
          <Input
            type="password"
            required
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="bg-white/5"
            autoComplete="current-password"
          />
          <Button className="w-full" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in to Platform"}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Looking for the product?{" "}
          <Link href="/login" className="text-teal-300 hover:underline">
            Customer sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
