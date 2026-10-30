"use client";

import { useState, type FormEvent } from "react";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

export default function ContactPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.submitContactRequest({
        name,
        company: company || undefined,
        email,
        team_size: teamSize || undefined,
        message,
      });
      setSent(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Unable to send request.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <section className="mx-auto max-w-xl px-4 py-20 sm:px-6">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold text-white">
            Request Demo
          </h1>
          <PrivateBetaBadge variant="marketing" />
        </div>
        <p className="text-slate-400">
          Tell us about your team — we typically reply within one business day.
        </p>
        {sent ? (
          <p className="mt-8 rounded-xl border border-teal-400/30 bg-teal-400/10 p-4 text-teal-100">
            Thanks — we received your request.
          </p>
        ) : (
          <form className="mt-8 space-y-4" onSubmit={onSubmit}>
            <Input
              name="name"
              placeholder="Name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-white/5"
            />
            <Input
              name="company"
              placeholder="Company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="bg-white/5"
            />
            <Input
              name="email"
              type="email"
              placeholder="Work email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-white/5"
            />
            <Input
              name="team_size"
              placeholder="Team size (e.g. 1–10, 11–50)"
              value={teamSize}
              onChange={(e) => setTeamSize(e.target.value)}
              className="bg-white/5"
            />
            <textarea
              name="message"
              required
              minLength={10}
              placeholder="Message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="min-h-32 w-full rounded-md border border-input bg-white/5 px-3 py-2 text-sm"
            />
            {error ? (
              <p className="rounded-md border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-200">
                {error}
              </p>
            ) : null}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Sending…" : "Request Demo"}
            </Button>
          </form>
        )}
      </section>
      <MarketingFooter />
    </div>
  );
}
