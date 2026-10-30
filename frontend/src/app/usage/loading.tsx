import { AppShell } from "@/components/layout/app-shell";
import { UsageSkeleton } from "@/components/loading";

export default function UsageLoading() {
  return (
    <AppShell>
      <UsageSkeleton />
    </AppShell>
  );
}
