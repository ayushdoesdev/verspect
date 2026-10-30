"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Activity, Github } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";

function SignupInner() {
  const auth = useAuth();
  const params = useSearchParams();
  const plan = params.get("plan");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function github() {
    setLoading(true);
    setError(null);
    try {
      const { authorization_url } = await api.getAuthUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub signup failed");
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
      setError(err instanceof Error ? err.message : "Google signup failed");
      setLoading(false);
    }
  }

  async function register(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const tokens = await api.register({ email, password, name });
      await auth.completeSignIn({
        access: tokens.access_token,
        refresh: tokens.refresh_token,
        user: tokens.user,
        redirectTo: plan ? `/billing?plan=${plan}` : "/onboarding",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
      setLoading(false);
    }
  }

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
            <h1 className="text-lg font-semibold text-white">Create your account</h1>
            <p className="text-sm text-slate-400">
              {plan
                ? `Continue to ${plan.charAt(0).toUpperCase()}${plan.slice(1)} after signup.`
                : "Start a 7-day evaluation — no credit card."}
            </p>
          </div>
        </div>
        {error ? (
          <div className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : null}
        <div className="space-y-2">
          <Button className="w-full" variant="secondary" onClick={github} disabled={loading}>
            <Github className="h-4 w-4" /> Continue with GitHub
          </Button>
          <Button className="w-full" variant="secondary" onClick={google} disabled={loading}>
            Continue with Google
          </Button>
        </div>
        <div className="my-5 text-center text-xs text-slate-500">or email</div>
        <form className="space-y-3" onSubmit={register}>
          <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} className="bg-white/5" />
          <Input
            type="email"
            required
            placeholder="Work email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="bg-white/5"
          />
          <Input
            type="password"
            required
            minLength={8}
            placeholder="Password (min 8)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="bg-white/5"
          />
          <Button className="w-full" type="submit" disabled={loading}>
            {loading ? "Creating…" : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="text-teal-300">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<AuthLoadingScreen message="Loading…" />}>
      <SignupInner />
    </Suspense>
  );
}
