"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminStat } from "@/components/admin/admin-table";
import { ErrorState } from "@/components/loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminHealthPage() {
  const overview = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: api.adminOverview,
    refetchInterval: 15_000,
  });
  const analytics = useQuery({
    queryKey: ["admin", "analytics", "health"],
    queryFn: () => api.adminAnalytics(7),
  });

  if (overview.isError) {
    return (
      <>
        <AdminPageHeader title="System Health" />
        <ErrorState title="Failed to load health" onRetry={() => overview.refetch()} />
      </>
    );
  }

  const o = overview.data;
  const failed = analytics.data?.failed_jobs || [];

  return (
    <>
      <AdminPageHeader
        title="System Health"
        description="Infrastructure and job pipeline status."
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <AdminStat label="Workers" value={o?.workers ?? "—"} />
        <AdminStat label="Redis" value={o?.redis ?? "—"} />
        <AdminStat label="Database" value={o?.database ?? "—"} />
        <AdminStat label="Queue / active scans" value={o?.active_scans ?? "—"} />
        <AdminStat label="Running scans" value={o?.active_scans ?? "—"} />
        <AdminStat label="Failed scans (today)" value={o?.failed_jobs ?? "—"} />
        <AdminStat label="Daily scans" value={o?.daily_scans ?? "—"} />
        <AdminStat label="Repository scans (total)" value={o?.repository_scans ?? "—"} />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm">Recent failed jobs (7d)</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-1 pr-4">Date</th>
                <th className="py-1">Count</th>
              </tr>
            </thead>
            <tbody>
              {failed.map((r) => (
                <tr key={r.date} className="border-t border-border/50">
                  <td className="py-1.5 pr-4">{r.date}</td>
                  <td className="py-1.5">{r.count}</td>
                </tr>
              ))}
              {!failed.length ? (
                <tr>
                  <td colSpan={2} className="py-3 text-muted-foreground">
                    No recent failures
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </>
  );
}
