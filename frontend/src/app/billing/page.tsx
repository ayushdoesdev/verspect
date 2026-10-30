"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useJobs } from "@/lib/jobs/jobs-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  BillingSkeleton,
  ErrorState,
  LoadingButton,
  LoadingCopy,
  ListSkeleton,
} from "@/components/loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type CheckoutPlan = "starter" | "pro" | "team";

const PLAN_ORDER = ["free", "starter", "pro", "team", "enterprise"] as const;

function planLabel(plan: string) {
  if (plan === "free") return "Evaluation";
  return plan.charAt(0).toUpperCase() + plan.slice(1);
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function BillingPage() {
  const params = useSearchParams();
  const qc = useQueryClient();
  const { toast } = useJobs();
  const auth = useRequireAuth();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const sub = useQuery({
    queryKey: ["subscription"],
    queryFn: api.subscription,
    enabled: auth.isAuthenticated,
  });
  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: api.usage,
    enabled: auth.isAuthenticated,
  });
  const invoices = useQuery({
    queryKey: ["invoices"],
    queryFn: api.invoices,
    enabled: auth.isAuthenticated,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (params.get("checkout") === "success") {
      qc.invalidateQueries({ queryKey: ["subscription"] });
      qc.invalidateQueries({ queryKey: ["usage"] });
      toast("Subscription updated", { tone: "success" });
    }
  }, [params, qc, toast]);

  async function refreshBilling() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["subscription"] }),
      qc.invalidateQueries({ queryKey: ["usage"] }),
      qc.invalidateQueries({ queryKey: ["invoices"] }),
    ]);
  }

  async function checkout(plan: CheckoutPlan, interval: "month" | "year") {
    setBusy(true);
    setError(null);
    try {
      const res = await api.checkout({ plan, interval });
      window.location.href = res.url;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Checkout failed";
      setError(message);
      toast("Unable to start checkout", {
        tone: "error",
        description: message,
        actionLabel: "Retry",
      });
      setBusy(false);
    }
  }

  async function changePlan(plan: CheckoutPlan | "free") {
    setBusy(true);
    setError(null);
    try {
      const res = await api.changePlan({ plan, interval: "month" });
      if (res.checkout_url && res.action === "checkout_required") {
        window.location.href = res.checkout_url;
        return;
      }
      toast(res.message || "Plan updated", {
        tone: res.action.includes("scheduled") ? "info" : "success",
      });
      await refreshBilling();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Plan change failed";
      setError(message);
      toast("Unable to change plan", { tone: "error", description: message });
    } finally {
      setBusy(false);
    }
  }

  async function cancelSub() {
    if (
      !window.confirm(
        "Cancel at the end of your billing period? You'll keep access until then, and all data is retained.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.cancelSubscription();
      toast(res.message || "Cancellation scheduled", { tone: "info" });
      await refreshBilling();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Cancel failed";
      setError(message);
      toast("Unable to cancel", { tone: "error", description: message });
    } finally {
      setBusy(false);
    }
  }

  async function reactivate() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.reactivateSubscription();
      toast(res.message || "Subscription reactivated", { tone: "success" });
      await refreshBilling();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Reactivate failed";
      setError(message);
      toast("Unable to reactivate", { tone: "error", description: message });
    } finally {
      setBusy(false);
    }
  }

  async function clearPending() {
    setBusy(true);
    try {
      const res = await api.clearPendingPlanChange();
      toast(res.message || "Scheduled change cleared", { tone: "success" });
      await refreshBilling();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to clear change";
      toast(message, { tone: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function portal() {
    setBusy(true);
    try {
      const res = await api.billingPortal();
      window.location.href = res.url;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Portal failed";
      setError(message);
      toast("Billing portal unavailable", { tone: "error", description: message });
      setBusy(false);
    }
  }

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <BillingSkeleton />
      </AppShell>
    );
  }

  if ((me.isLoading || sub.isLoading) && !sub.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <BillingSkeleton />
      </AppShell>
    );
  }

  if (sub.isError && !sub.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <PageHeader
          title="Billing"
          description="Manage your subscription, invoices, and commercial launch plans."
        />
        <ErrorState
          title="Unable to load billing information"
          description={(sub.error as Error)?.message || "Try again in a moment."}
          onRetry={() => sub.refetch()}
        />
      </AppShell>
    );
  }

  const plan = (sub.data?.plan || "free").toLowerCase();
  const limits = (sub.data?.limits || {}) as Record<string, unknown>;
  const highlight = params.get("plan");
  const pendingMessage = sub.data?.pending_change_message;
  const canReactivate = Boolean(sub.data?.can_reactivate);
  const canCancel = Boolean(sub.data?.can_cancel);

  const upgradeTargets = (["starter", "pro", "team"] as CheckoutPlan[]).filter(
    (p) => PLAN_ORDER.indexOf(p) > PLAN_ORDER.indexOf(plan as (typeof PLAN_ORDER)[number]),
  );
  const downgradeTargets = (["pro", "starter"] as CheckoutPlan[]).filter(
    (p) => PLAN_ORDER.indexOf(p) < PLAN_ORDER.indexOf(plan as (typeof PLAN_ORDER)[number]) && p !== plan,
  );

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader
        title="Billing"
        description="Manage your subscription, invoices, and commercial launch plans."
      />
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {pendingMessage ? (
        <Card className="mb-4 border-primary/30 bg-primary/5">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-foreground">{pendingMessage}</p>
            <div className="flex flex-wrap gap-2">
              {canReactivate ? (
                <LoadingButton loading={busy} loadingText="Reactivating…" onClick={reactivate}>
                  Reactivate Subscription
                </LoadingButton>
              ) : null}
              {sub.data?.pending_change_type === "downgrade" ? (
                <LoadingButton
                  loading={busy}
                  loadingText="Clearing…"
                  variant="outline"
                  onClick={clearPending}
                >
                  Keep current plan
                </LoadingButton>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Current plan</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-2xl font-semibold">{planLabel(plan)}</span>
              <Badge>{sub.data?.status || "active"}</Badge>
              {sub.data?.cancel_at_period_end ? (
                <Badge className="border-warning/40 bg-warning/10 text-warning">
                  Cancels at period end
                </Badge>
              ) : null}
            </div>

            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">Price</dt>
                <dd className="font-medium">
                  {plan === "free"
                    ? "Free"
                    : sub.data?.price_label
                      ? `${sub.data.price_label}/mo`
                      : "—"}
                  {plan === "team" ? " per user" : ""}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Status</dt>
                <dd className="font-medium capitalize">{sub.data?.status || "active"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Renewal date</dt>
                <dd className="font-medium">{formatDate(sub.data?.current_period_end)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Next invoice</dt>
                <dd className="font-medium">
                  {sub.data?.cancel_at_period_end
                    ? "None (canceling)"
                    : formatDate(sub.data?.next_invoice_at || sub.data?.current_period_end)}
                </dd>
              </div>
            </dl>

            {sub.data?.evaluation_expired ? (
              <p className="text-amber-600 dark:text-amber-400">
                Evaluation ended
                {sub.data.trial_ends_at
                  ? ` on ${formatDate(sub.data.trial_ends_at)}`
                  : ""}
                . Existing data remains readable — upgrade to restore scans and imports.
              </p>
            ) : sub.data?.trial_ends_at && plan === "free" ? (
              <p className="text-muted-foreground">
                Evaluation ends {formatDate(sub.data.trial_ends_at)}
              </p>
            ) : null}

            <div className="flex flex-wrap gap-2 border-t border-border/50 pt-3">
              {upgradeTargets.map((p) => (
                <LoadingButton
                  key={p}
                  loading={busy}
                  loadingText="Updating…"
                  className={highlight === p ? "ring-2 ring-primary" : undefined}
                  onClick={() => (plan === "free" ? checkout(p, "month") : changePlan(p))}
                >
                  Upgrade to {planLabel(p)}
                </LoadingButton>
              ))}
              {downgradeTargets.map((p) => (
                <LoadingButton
                  key={p}
                  loading={busy}
                  loadingText="Scheduling…"
                  variant="secondary"
                  onClick={() => changePlan(p)}
                >
                  Downgrade to {planLabel(p)}
                </LoadingButton>
              ))}
              {canCancel ? (
                <LoadingButton
                  loading={busy}
                  loadingText="Scheduling…"
                  variant="outline"
                  onClick={cancelSub}
                >
                  Cancel Subscription
                </LoadingButton>
              ) : null}
              {canReactivate && !pendingMessage ? (
                <LoadingButton loading={busy} loadingText="Reactivating…" onClick={reactivate}>
                  Reactivate Subscription
                </LoadingButton>
              ) : null}
              <LoadingButton
                loading={busy}
                loadingText="Opening…"
                variant="outline"
                onClick={portal}
              >
                Customer portal
              </LoadingButton>
              <Link
                href="/pricing"
                className={cn(buttonVariants({ variant: "ghost" }), "h-9")}
              >
                View pricing
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Usage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            {usage.isLoading && !usage.data ? (
              <LoadingCopy>Loading usage…</LoadingCopy>
            ) : (
              <>
                <p>
                  Repositories (active): {usage.data?.repositories_used ?? "—"} /{" "}
                  {usage.data?.repositories_limit ?? "Unlimited"}
                </p>
                <p>
                  Members: {usage.data?.members_used ?? "—"} /{" "}
                  {usage.data?.members_limit ?? "Unlimited"}
                </p>
                <p>
                  Scans this month: {usage.data?.monthly_scans_used ?? 0} /{" "}
                  {usage.data?.monthly_scan_limit ?? "Unlimited"}
                </p>
                <p className="pt-2 text-xs">
                  Downgrades never delete data. Excess repositories are archived so you can
                  choose which stay active.
                </p>
              </>
            )}
            <div className="border-t border-border/50 pt-3 space-y-1">
              <p className="text-foreground text-xs font-medium">Entitlements</p>
              <p>Upgrade Simulator: {String(limits.upgrade_simulator ?? true)}</p>
              <p>AI Upgrade Advisor: {String(limits.ai_enabled ?? false)}</p>
              <p>AI Migration Assistant: {String(limits.ai_migration_assistant ?? false)}</p>
              <p>GitHub webhooks / scheduled scans: {String(limits.webhooks ?? limits.scheduled_scans ?? false)}</p>
              <p>
                Teams / RBAC: {String(limits.teams_enabled ?? false)} /{" "}
                {String(limits.rbac ?? false)}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Invoices</CardTitle>
        </CardHeader>
        <CardContent>
          {invoices.isLoading && !invoices.data ? (
            <div className="space-y-2">
              <LoadingCopy>Loading billing information…</LoadingCopy>
              <ListSkeleton rows={3} />
            </div>
          ) : invoices.isError && !invoices.data ? (
            <ErrorState
              title="Unable to load invoices"
              description={(invoices.error as Error)?.message || "Try again."}
              onRetry={() => invoices.refetch()}
            />
          ) : (invoices.data || []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No invoices yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {invoices.data!.map((inv) => (
                <li
                  key={inv.id}
                  className="flex items-center justify-between border-b border-border/50 py-2"
                >
                  <span>
                    {inv.number || inv.id.slice(0, 8)} · {inv.status} · ${inv.amount_paid}
                  </span>
                  {inv.hosted_invoice_url ? (
                    <a
                      className="text-primary"
                      href={inv.hosted_invoice_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </AppShell>
  );
}
