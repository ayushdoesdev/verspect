"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminStat } from "@/components/admin/admin-table";
import { ErrorState } from "@/components/loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminAnalyticsPage() {
  const analytics = useQuery({
    queryKey: ["admin", "analytics"],
    queryFn: () => api.adminAnalytics(14),
  });

  if (analytics.isError) {
    return (
      <>
        <AdminPageHeader title="Analytics" />
        <ErrorState title="Failed to load analytics" onRetry={() => analytics.refetch()} />
      </>
    );
  }

  const a = analytics.data;

  return (
    <>
      <AdminPageHeader title="Analytics" description="14-day platform activity." />
      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <AdminStat
          label="Avg scan duration"
          value={a?.average_scan_duration_seconds != null ? `${a.average_scan_duration_seconds}s` : "—"}
        />
        <AdminStat
          label="Avg simulation duration"
          value={
            a?.average_simulation_duration_seconds != null
              ? `${a.average_simulation_duration_seconds}s`
              : "—"
          }
        />
      </div>
      <div className="space-y-4">
        {(
          [
            ["Daily users", a?.daily_users],
            ["Daily scans", a?.daily_scans],
            ["Daily simulations", a?.daily_simulations],
            ["AI Advisor usage", a?.ai_advisor_usage],
            ["Failed jobs", a?.failed_jobs],
          ] as const
        ).map(([label, rows]) => (
          <Card key={label}>
            <CardHeader>
              <CardTitle className="text-sm">{label}</CardTitle>
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
                  {(rows || []).map((r) => (
                    <tr key={r.date} className="border-t border-border/50">
                      <td className="py-1.5 pr-4">{r.date}</td>
                      <td className="py-1.5">{r.count}</td>
                    </tr>
                  ))}
                  {!rows?.length ? (
                    <tr>
                      <td colSpan={2} className="py-3 text-muted-foreground">
                        No data yet
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
