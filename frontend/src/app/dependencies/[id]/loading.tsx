import { AppShell } from "@/components/layout/app-shell";
import { DependencyPageSkeleton } from "@/components/loading";

export default function DependencyDetailLoading() {
  return (
    <AppShell>
      <DependencyPageSkeleton />
    </AppShell>
  );
}
