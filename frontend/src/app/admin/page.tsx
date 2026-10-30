"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminStat, AdminTable } from "@/components/admin/admin-table";
import { ErrorState } from "@/components/loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminDashboardPage() {
  const overview = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: api.adminOverview,
  });
  const feedback = useQuery({
    queryKey: ["admin", "feedback", "open-count"],
    queryFn: () => api.adminFeedback("?status=open&page_size=5"),
  });
  const contacts = useQuery({
    queryKey: ["admin", "contacts", "recent"],
    queryFn: () => api.adminContactRequests("?page_size=5"),
  });
  const users = useQuery({
    queryKey: ["admin", "users", "recent"],
    queryFn: () => api.adminUsers("?page_size=8"),
  });

  if (overview.isError) {
    return (
      <>
        <AdminPageHeader title="Dashboard" />
        <ErrorState title="Failed to load overview" onRetry={() => overview.refetch()} />
      </>
    );
  }

  const o = overview.data;

  return (
    <>
      <AdminPageHeader
        title="Dashboard"
        description="Platform overview for Private Beta operations."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <AdminStat label="Total Users" value={o?.total_users ?? "—"} />
        <AdminStat label="Verified Users" value={o?.verified_users ?? "—"} />
        <AdminStat label="Organizations" value={o?.organizations ?? "—"} />
        <AdminStat label="Repositories" value={o?.repositories ?? "—"} />
        <AdminStat label="Repository Scans Today" value={o?.daily_scans ?? "—"} />
        <AdminStat label="AI Advisor Runs" value={o?.ai_advisor_jobs ?? "—"} />
        <AdminStat label="Simulator Runs" value={o?.upgrade_simulations ?? "—"} />
        <AdminStat label="Feedback Open" value={feedback.data?.total ?? "—"} />
        <AdminStat label="Contact Requests" value={contacts.data?.total ?? "—"} />
        <AdminStat label="Workers Online" value={o?.workers ?? "—"} />
        <AdminStat label="Redis" value={o?.redis ?? "—"} />
        <AdminStat label="Database" value={o?.database ?? "—"} />
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent signups</CardTitle>
          </CardHeader>
          <CardContent>
            <AdminTable
              loading={users.isLoading}
              error={users.isError}
              onRetry={() => users.refetch()}
              headers={["Name", "Email", "Plan", "Created"]}
              rows={(users.data?.items || []).map((u) => [
                u.name || "—",
                u.email,
                u.plan,
                new Date(u.created_at).toLocaleString(),
              ])}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Open feedback</CardTitle>
          </CardHeader>
          <CardContent>
            <AdminTable
              loading={feedback.isLoading}
              error={feedback.isError}
              onRetry={() => feedback.refetch()}
              headers={["Title", "Priority", "Email", "Created"]}
              rows={(feedback.data?.items || []).map((f) => [
                f.title,
                f.priority || "medium",
                f.email,
                new Date(f.created_at).toLocaleString(),
              ])}
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
