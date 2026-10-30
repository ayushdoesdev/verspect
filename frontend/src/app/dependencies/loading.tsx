import { AppShell } from "@/components/layout/app-shell";
import { DependenciesSkeleton } from "@/components/loading";

export default function DependenciesLoading() {
  return (
    <AppShell>
      <DependenciesSkeleton />
    </AppShell>
  );
}
