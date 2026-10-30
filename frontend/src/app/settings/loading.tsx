import { AppShell } from "@/components/layout/app-shell";
import { SettingsSkeleton } from "@/components/loading";

export default function SettingsLoading() {
  return (
    <AppShell>
      <SettingsSkeleton />
    </AppShell>
  );
}
