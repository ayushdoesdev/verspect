import { AppShell } from "@/components/layout/app-shell";
import { DashboardSkeleton } from "@/components/loading";

export default function DashboardLoading() {
  return (
    <AppShell>
      <DashboardSkeleton />
    </AppShell>
  );
}
