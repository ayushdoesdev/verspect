"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { ErrorState, SettingsSkeleton } from "@/components/loading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  const qc = useQueryClient();
  const auth = useRequireAuth();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const org = useQuery({
    queryKey: ["current-org"],
    queryFn: api.currentOrganization,
    enabled: auth.isAuthenticated,
  });

  const [emailNotifications, setEmailNotifications] = useState(true);
  const [slackNotifications, setSlackNotifications] = useState(false);
  const [slackWebhook, setSlackWebhook] = useState("");
  const [notifyCve, setNotifyCve] = useState(true);
  const [notifyMajor, setNotifyMajor] = useState(true);
  const [notifyLicense, setNotifyLicense] = useState(true);
  const [rejectLicenses, setRejectLicenses] = useState("");
  const [warnLicenses, setWarnLicenses] = useState("");

  useEffect(() => {
    if (!me.data) return;
    setEmailNotifications(me.data.email_notifications);
    setSlackNotifications(me.data.slack_notifications);
    setSlackWebhook(me.data.slack_webhook_url || "");
    setNotifyCve(me.data.notify_on_critical_cve);
    setNotifyMajor(me.data.notify_on_major_release);
    setNotifyLicense(me.data.notify_on_license_violation);
  }, [me.data]);

  useEffect(() => {
    const policy = org.data?.license_policy;
    if (!policy) return;
    setRejectLicenses((policy.reject || []).join(", "));
    setWarnLicenses((policy.warn || []).join(", "));
  }, [org.data]);

  const save = useMutation({
    mutationFn: () =>
      api.updateSettings({
        email_notifications: emailNotifications,
        slack_notifications: slackNotifications,
        slack_webhook_url: slackWebhook || null,
        notify_on_critical_cve: notifyCve,
        notify_on_major_release: notifyMajor,
        notify_on_license_violation: notifyLicense,
      } as never),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });

  const saveLicense = useMutation({
    mutationFn: () => {
      if (!org.data?.id) throw new Error("No organization");
      const split = (s: string) =>
        s
          .split(/[,;\n]/)
          .map((x) => x.trim())
          .filter(Boolean);
      return api.updateLicensePolicy(org.data.id, {
        reject: split(rejectLicenses),
        warn: split(warnLicenses),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["current-org"] });
      qc.invalidateQueries({ queryKey: ["organizations"] });
    },
  });

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <SettingsSkeleton />
      </AppShell>
    );
  }

  if (me.isLoading && !me.data) {
    return (
      <AppShell userLogin={auth.user?.github_login}>
        <SettingsSkeleton />
      </AppShell>
    );
  }

  if (me.isError && !me.data) {
    return (
      <AppShell userLogin={auth.user?.github_login}>
        <PageHeader title="Settings" description="Notification preferences, account, and AI provider status." />
        <ErrorState
          title="Unable to load settings"
          description={(me.error as Error)?.message || "Try again in a moment."}
          onRetry={() => me.refetch()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader title="Settings" description="Notification preferences, account, and AI provider status." />
      <div className="mb-4">
        <Link
          href="/settings/ai"
          className="text-sm font-medium text-primary hover:underline"
        >
          AI Settings → provider, model & connection status
        </Link>
      </div>
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>
            Alerts for critical CVEs, major releases, and license violations.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Toggle
            label="Email notifications"
            checked={emailNotifications}
            onChange={setEmailNotifications}
          />
          <Toggle
            label="Slack notifications"
            checked={slackNotifications}
            onChange={setSlackNotifications}
          />
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">Slack webhook URL</label>
            <Input
              value={slackWebhook}
              onChange={(e) => setSlackWebhook(e.target.value)}
              placeholder="https://hooks.slack.com/services/…"
            />
          </div>
          <Toggle label="Notify on critical CVE" checked={notifyCve} onChange={setNotifyCve} />
          <Toggle label="Notify on major release" checked={notifyMajor} onChange={setNotifyMajor} />
          <Toggle
            label="Notify on license violation"
            checked={notifyLicense}
            onChange={setNotifyLicense}
          />
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : save.isSuccess ? "Saved" : "Save settings"}
          </Button>
        </CardContent>
      </Card>

      <Card className="mt-6 max-w-xl">
        <CardHeader>
          <CardTitle>Organization license policy</CardTitle>
          <CardDescription>
            SPDX-like identifiers applied on the next repository scan. Source:{" "}
            {org.data?.license_policy?.source || "loading…"}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">Reject (comma-separated)</label>
            <Input
              value={rejectLicenses}
              onChange={(e) => setRejectLicenses(e.target.value)}
              placeholder="GPL-3.0, AGPL-3.0"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">Warn (comma-separated)</label>
            <Input
              value={warnLicenses}
              onChange={(e) => setWarnLicenses(e.target.value)}
              placeholder="LGPL-3.0, LGPL-2.1"
            />
          </div>
          <Button
            onClick={() => saveLicense.mutate()}
            disabled={saveLicense.isPending || !org.data?.id}
          >
            {saveLicense.isPending
              ? "Saving…"
              : saveLicense.isSuccess
                ? "Saved"
                : "Save license policy"}
          </Button>
          {saveLicense.isError ? (
            <p className="text-sm text-destructive">
              {(saveLicense.error as Error).message || "Unable to save policy"}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 text-sm">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}
