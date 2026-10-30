import { AppShell } from "@/components/layout/app-shell";
import { MigrationAssistantSkeleton } from "@/components/loading";

export default function MigrationAssistantLoading() {
  return (
    <AppShell>
      <MigrationAssistantSkeleton />
    </AppShell>
  );
}
