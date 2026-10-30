import { AppShell } from "@/components/layout/app-shell";
import { RepositoryPageSkeleton } from "@/components/loading";

export default function RepositoryDetailLoading() {
  return (
    <AppShell>
      <RepositoryPageSkeleton />
    </AppShell>
  );
}
