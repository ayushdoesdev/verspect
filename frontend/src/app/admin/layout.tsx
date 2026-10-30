"use client";

import { usePathname } from "next/navigation";
import { RequirePlatformAdmin } from "@/components/admin/require-platform-admin";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/admin/login") {
    return <>{children}</>;
  }
  return <RequirePlatformAdmin>{children}</RequirePlatformAdmin>;
}
