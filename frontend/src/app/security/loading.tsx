import { AppShell } from "@/components/layout/app-shell";
import { SecuritySkeleton } from "@/components/loading";

export default function SecurityLoading() {
  return (
    <AppShell>
      <SecuritySkeleton />
    </AppShell>
  );
}
