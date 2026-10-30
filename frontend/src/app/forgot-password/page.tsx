"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#070b12] px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.04] p-8">
        <h1 className="text-xl font-semibold text-white">Reset password</h1>
        <p className="mt-2 text-sm text-slate-400">We&apos;ll email a reset link if the account exists.</p>
        {done ? (
          <p className="mt-6 text-sm text-teal-200">If that email exists, a reset link has been sent.</p>
        ) : (
          <form
            className="mt-6 space-y-3"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.forgotPassword(email);
                setDone(true);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Request failed");
              }
            }}
          >
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="bg-white/5" />
            <Button type="submit" className="w-full">Send reset link</Button>
          </form>
        )}
        <Link href="/login" className="mt-4 inline-block text-xs text-slate-500 hover:text-teal-300">Back to sign in</Link>
      </div>
    </div>
  );
}
