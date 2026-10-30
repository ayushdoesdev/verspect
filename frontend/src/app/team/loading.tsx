import { AppShell } from "@/components/layout/app-shell";
import { OrganizationsSkeleton } from "@/components/loading";

export default function TeamLoading() {
  return (
    <AppShell>
      <OrganizationsSkeleton />
    </AppShell>
  );
}
