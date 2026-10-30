import { AppShell } from "@/components/layout/app-shell";
import { BillingSkeleton } from "@/components/loading";

export default function BillingLoading() {
  return (
    <AppShell>
      <BillingSkeleton />
    </AppShell>
  );
}
