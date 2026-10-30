import { AppShell } from "@/components/layout/app-shell";
import { SearchSkeleton } from "@/components/loading";

export default function SearchLoading() {
  return (
    <AppShell>
      <SearchSkeleton />
    </AppShell>
  );
}
