"use client";

import { useState } from "react";
import Link from "next/link";
import { Activity, Github } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function github() {
    setLoading(true);
    setError(null);
    try {
      const { authorization_url } = await api.getAuthUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start GitHub login");
      setLoading(false);
    }
  }

  async function google() {
    setLoading(true);
    setError(null);
    try {
      const { authorization_url } = await api.getGoogleAuthUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google login failed");
      setLoading(false);
    }
  }

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const tokens = await api.login({ email, password, remember_me: remember });
      if (!tokens.access_token || !tokens.refresh_token) {
        throw new Error("Login response missing tokens");
      }
      // Single navigation after workspace hydrate — never bounce through Login again
      await auth.completeSignIn({
        access: tokens.access_token,
        refresh: tokens.refresh_token,
        user: tokens.user,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  // AuthInitializer already redirects authenticated users; avoid form flash
  if (auth.isAuthenticated || auth.isLoading || auth.isTransitioning) {
    return null;
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#070b12] px-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(61,214,198,0.12),transparent_50%)]" />
      <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.04] p-8 backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-400/15 text-teal-300">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">Welcome back</h1>
            <p className="text-sm text-slate-400">Sign in to Dependency Intelligence</p>
          </div>
        </div>
        {error ? (
          <div className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : null}
        <div className="space-y-2">
          <Button className="w-full" onClick={github} disabled={loading}>
            <Github className="h-4 w-4" /> Continue with GitHub
          </Button>
          <Button className="w-full" variant="secondary" onClick={google} disabled={loading}>
            Continue with Google
          </Button>
        </div>
        <div className="my-5 text-center text-xs text-slate-500">or email</div>
        <form className="space-y-3" onSubmit={login}>
          <Input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="bg-white/5"
          />
          <Input
            type="password"
            required
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="bg-white/5"
          />
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            Remember me
          </label>
          <Button className="w-full" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <div className="mt-4 flex justify-between text-xs text-slate-500">
          <Link href="/forgot-password" className="hover:text-teal-300">
            Forgot password?
          </Link>
          <Link href="/signup" className="hover:text-teal-300">
            Create account
          </Link>
        </div>
      </div>
    </div>
  );
}
