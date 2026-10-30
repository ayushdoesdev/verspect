"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { useJobs } from "@/lib/jobs/jobs-context";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  ErrorState,
  ListSkeleton,
  LoadingButton,
  LoadingCopy,
  OrganizationsSkeleton,
} from "@/components/loading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TeamPage() {
  const qc = useQueryClient();
  const { toast } = useJobs();
  const auth = useRequireAuth();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: auth.isAuthenticated });
  const org = useQuery({ queryKey: ["org-current"], queryFn: api.currentOrganization, enabled: auth.isAuthenticated });
  const members = useQuery({
    queryKey: ["org-members", org.data?.id],
    queryFn: () => api.orgMembers(org.data!.id),
    enabled: auth.isAuthenticated && !!org.data?.id,
  });
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("developer");
  const [error, setError] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);

  async function invite() {
    if (!org.data) return;
    setError(null);
    setInviting(true);
    try {
      await api.inviteMember(org.data.id, { email, role });
      setEmail("");
      qc.invalidateQueries({ queryKey: ["org-members"] });
      toast("Member invited", { tone: "success", description: `Invitation sent to ${email}` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invite failed";
      setError(message);
      toast("Unable to invite member", { tone: "error", description: message, actionLabel: "Retry" });
    } finally {
      setInviting(false);
    }
  }

  if (auth.isLoading || !auth.isAuthenticated) {
    return (
      <AppShell>
        <OrganizationsSkeleton />
      </AppShell>
    );
  }

  if ((me.isLoading || org.isLoading) && !org.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <OrganizationsSkeleton />
      </AppShell>
    );
  }

  if (org.isError && !org.data) {
    return (
      <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
        <PageHeader title="Team" description="Organization members and invitations" />
        <ErrorState
          title="Unable to load organization"
          description={(org.error as Error)?.message || "Try again in a moment."}
          onRetry={() => org.refetch()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell userLogin={auth.user?.github_login || me.data?.github_login}>
      <PageHeader
        title="Team"
        description={org.data ? `${org.data.name} · ${org.data.plan} plan` : "Organization members and invitations"}
      />
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Members</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {members.isLoading && !members.data ? (
              <div className="space-y-2">
                <LoadingCopy>Loading organization…</LoadingCopy>
                <ListSkeleton rows={3} />
              </div>
            ) : members.isError && !members.data ? (
              <ErrorState
                title="Unable to load members"
                description={(members.error as Error)?.message || "Try again."}
                onRetry={() => members.refetch()}
              />
            ) : (
              (members.data || []).map((m) => (
              <div key={m.id} className="flex items-center justify-between text-sm">
                <div>
                  <div className="font-medium">{m.name || m.github_login || m.email}</div>
                  <div className="text-xs text-muted-foreground">{m.email}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="capitalize text-muted-foreground">{m.role}</span>
                  {m.role !== "owner" ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await api.removeMember(org.data!.id, m.user_id);
                        qc.invalidateQueries({ queryKey: ["org-members"] });
                      }}
                    >
                      Remove
                    </Button>
                  ) : null}
                </div>
              </div>
            ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invite member</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input placeholder="email@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="admin">Admin</option>
              <option value="developer">Developer</option>
              <option value="viewer">Viewer</option>
            </select>
            <LoadingButton loading={inviting} loadingText="Sending…" onClick={invite} disabled={!email}>
              Send invitation
            </LoadingButton>
            <p className="text-xs text-muted-foreground">Team plan required for additional seats.</p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
