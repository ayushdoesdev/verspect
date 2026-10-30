"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { AiSettingsSkeleton, ErrorState, RefetchBar } from "@/components/loading";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function AISettingsPage() {
  const auth = useRequireAuth();
  const settings = useQuery({
    queryKey: ["ai-settings"],
    queryFn: api.aiSettings,
    enabled: auth.isAuthenticated,
    refetchInterval: 30_000,
  });
  const health = useQuery({
    queryKey: ["ai-health"],
    queryFn: api.aiHealth,
    enabled: auth.isAuthenticated,
    refetchInterval: 30_000,
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <AiSettingsSkeleton />
      </AppShell>
    );
  }

  if ((settings.isLoading || health.isLoading) && !settings.data && !health.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || auth.user?.email || undefined}>
        <AiSettingsSkeleton />
      </AppShell>
    );
  }

  if (settings.isError && health.isError && !settings.data && !health.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || auth.user?.email || undefined}>
        <PageHeader
          title="AI Settings"
          description="Provider configuration is server-side (AI_PROVIDER). This page shows live connection status."
        />
        <ErrorState
          title="Unable to load AI settings"
          description="Try refreshing the connection status."
          onRetry={() => {
            settings.refetch();
            health.refetch();
          }}
        />
      </AppShell>
    );
  }

  const s = settings.data;
  const h = health.data;
  const available = h?.available ?? s?.available ?? false;
  const status = h?.status || s?.connection_status || "unknown";

  return (
    <AppShell userLogin={auth.user?.github_login || auth.user?.email || undefined}>
      <PageHeader
        title="AI Settings"
        description="Provider configuration is server-side (AI_PROVIDER). This page shows live connection status."
      />
      <RefetchBar
        active={(settings.isFetching || health.isFetching) && !settings.isLoading}
        label="Updating AI status…"
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Link href="/settings" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
          ← Notification settings
        </Link>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            settings.refetch();
            health.refetch();
          }}
          disabled={settings.isFetching || health.isFetching}
        >
          <RefreshCw className={cn("h-4 w-4", (settings.isFetching || health.isFetching) && "animate-spin")} />
          Refresh
        </Button>
      </div>

      <div className="grid max-w-3xl gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Current Provider</CardTitle>
            <CardDescription>Active runtime provider (after fallbacks)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Configured" value={s?.configured_provider || "—"} />
            <Row label="Active" value={s?.active_provider || h?.provider || "—"} />
            <Row
              label="Fallbacks"
              value={(s?.fallback_providers || h?.fallbacks || []).join(" → ") || "—"}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Current Model</CardTitle>
            <CardDescription>Model resolved from config</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Configured" value={s?.configured_model || "—"} />
            <Row label="Active" value={s?.active_model || h?.model || "—"} />
            {s?.configured_provider === "ollama" || s?.active_provider === "ollama" ? (
              <>
                <Row label="Ollama URL" value={s?.ollama_base_url || "—"} />
                <Row label="Ollama model" value={s?.ollama_model || "—"} />
              </>
            ) : null}
          </CardContent>
        </Card>

        <Card className="sm:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-primary" />
              Connection Status
            </CardTitle>
            <CardDescription>Live probe via /api/ai/health</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              {available ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive">
                  <XCircle className="h-3.5 w-3.5" />
                  Unavailable
                </span>
              )}
              <span className="text-muted-foreground">status: {status}</span>
              {h?.latency_ms != null ? (
                <span className="tabular-nums text-muted-foreground">{h.latency_ms} ms</span>
              ) : null}
            </div>
            <p className="text-muted-foreground">{h?.message || s?.health_message || "—"}</p>
            <div className="rounded-lg border border-border/60 bg-background/40 p-3 text-xs text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">Switch providers</p>
              <p>
                Set <code className="text-foreground">AI_PROVIDER</code> in{" "}
                <code className="text-foreground">.env</code> to{" "}
                <code className="text-foreground">ollama</code>,{" "}
                <code className="text-foreground">gemini</code>,{" "}
                <code className="text-foreground">openai</code>,{" "}
                <code className="text-foreground">openrouter</code>, or{" "}
                <code className="text-foreground">groq</code>, then recreate backend/worker.
              </p>
              <p className="mt-2">
                Supported: {(s?.supported_providers || []).join(", ") || "ollama, openai, gemini, groq, openrouter"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[70%] break-all text-right font-medium">{value}</span>
    </div>
  );
}
