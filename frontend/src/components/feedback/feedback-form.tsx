"use client";

import { useEffect, useState, type FormEvent } from "react";
import { usePathname } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { APP_VERSION } from "@/lib/app-version";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { value: "bug_report", label: "Bug Report" },
  { value: "feature_request", label: "Feature Request" },
  { value: "improvement", label: "Improvement" },
  { value: "question", label: "Question" },
] as const;

const PRIORITIES = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
] as const;

export type FeedbackFormProps = {
  className?: string;
  onSuccess?: () => void;
  compact?: boolean;
};

export function FeedbackForm({ className, onSuccess, compact }: FeedbackFormProps) {
  const pathname = usePathname();
  const auth = useAuth();
  const [category, setCategory] = useState<string>("bug_report");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [repository, setRepository] = useState("");
  const [priority, setPriority] = useState<string>("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const browser =
    typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 120) : "unknown";

  useEffect(() => {
    if (auth.user?.email) setEmail(auth.user.email);
  }, [auth.user?.email]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      await api.submitFeedback({
        category,
        title,
        description,
        email,
        repository: repository || undefined,
        priority,
        page_url: typeof window !== "undefined" ? window.location.href : pathname,
        app_version: APP_VERSION,
        browser: typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 512) : undefined,
      });
      setSuccess(true);
      setTitle("");
      setDescription("");
      setRepository("");
      setPriority("medium");
      onSuccess?.();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Unable to submit feedback.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      data-testid="feedback-form"
      onSubmit={onSubmit}
      className={cn(compact ? "space-y-3" : "space-y-5", className)}
    >
      <div className="space-y-2">
        <div className="text-xs font-medium text-muted-foreground">
          {compact ? "Category" : "Feedback Categories"}
        </div>
        <div
          className={cn("grid gap-2", compact ? "grid-cols-2" : "sm:grid-cols-2")}
          role="radiogroup"
          aria-label="Category"
        >
          {CATEGORIES.map((c) => (
            <label
              key={c.value}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md border px-3 text-sm transition",
                compact ? "py-1.5" : "py-2",
                category === c.value
                  ? "border-primary/40 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:bg-accent/40",
              )}
            >
              <input
                type="radio"
                name="feedback-category"
                value={c.value}
                checked={category === c.value}
                onChange={() => setCategory(c.value)}
                className="accent-primary"
                required
              />
              {c.label}
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground">Title *</label>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Short summary"
          required
          minLength={3}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground">Description *</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What happened? What did you expect?"
          required
          minLength={10}
          maxLength={8000}
          rows={compact ? 3 : 6}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className={cn("grid gap-4", compact ? "grid-cols-1 sm:grid-cols-2" : "sm:grid-cols-2")}>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Email *</label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="you@company.com"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            Repository <span className="opacity-70">(optional)</span>
          </label>
          <Input
            value={repository}
            onChange={(e) => setRepository(e.target.value)}
            placeholder="owner/repo"
          />
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-xs font-medium text-muted-foreground">Priority</div>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Priority">
          {PRIORITIES.map((p) => (
            <label
              key={p.value}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition",
                priority === p.value
                  ? "border-primary/40 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:bg-accent/40",
              )}
            >
              <input
                type="radio"
                name="feedback-priority"
                value={p.value}
                checked={priority === p.value}
                onChange={() => setPriority(p.value)}
                className="accent-primary"
              />
              {p.label}
            </label>
          ))}
        </div>
      </div>

      {!compact ? (
        <div className="space-y-1 rounded-lg border border-border/60 bg-secondary/20 px-3 py-2 text-[11px] text-muted-foreground">
          <div>Current page: {pathname || "/"}</div>
          <div className="truncate">Browser: {browser}</div>
          <div>App version: {APP_VERSION}</div>
        </div>
      ) : null}

      {error ? (
        <div
          data-testid="feedback-error"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      ) : null}
      {success ? (
        <div
          data-testid="feedback-success"
          className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary"
        >
          Thanks — your feedback was submitted.
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" disabled={submitting} size={compact ? "sm" : "default"}>
          {submitting ? "Submitting…" : compact ? "Submit" : "Submit Feedback"}
        </Button>
      </div>
    </form>
  );
}
