"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminStat } from "@/components/admin/admin-table";
import { ErrorState } from "@/components/loading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminWorkersPage() {
  const overview = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: api.adminOverview,
    refetchInterval: 15_000,
  });

  if (overview.isError) {
    return (
      <>
        <AdminPageHeader title="Workers" />
        <ErrorState title="Failed to load worker status" onRetry={() => overview.refetch()} />
      </>
    );
  }

  const o = overview.data;

  return (
    <>
      <AdminPageHeader
        title="Workers"
        description="Background processing capacity for scans and simulations."
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <AdminStat label="Workers" value={o?.workers ?? "—"} />
        <AdminStat label="Active scans" value={o?.active_scans ?? "—"} />
        <AdminStat label="Failed jobs (today)" value={o?.failed_jobs ?? "—"} />
        <AdminStat label="Redis" value={o?.redis ?? "—"} />
      </div>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm">Notes</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Worker liveness is reported by the platform overview health probe. When workers are
          offline, new scans remain queued until capacity returns.
        </CardContent>
      </Card>
    </>
  );
}
