import { AppShell } from "@/components/layout/app-shell";
import { SessionSkeleton } from "@/components/loading";

export default function RepositoriesLoading() {
  return (
    <AppShell>
      <SessionSkeleton variant="repositories" />
    </AppShell>
  );
}
