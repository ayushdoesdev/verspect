import { AppShell } from "@/components/layout/app-shell";
import { UpgradeSimulatorSkeleton } from "@/components/loading";

export default function UpgradeSimulatorLoading() {
  return (
    <AppShell>
      <UpgradeSimulatorSkeleton />
    </AppShell>
  );
}
