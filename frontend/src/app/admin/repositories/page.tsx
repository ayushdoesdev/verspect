"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { Input } from "@/components/ui/input";

export default function AdminRepositoriesPage() {
  const [q, setQ] = useState("");
  const repos = useQuery({
    queryKey: ["admin", "repos", q],
    queryFn: () => api.adminRepositories(q ? `?q=${encodeURIComponent(q)}` : ""),
  });

  return (
    <>
      <AdminPageHeader
        title="Repositories"
        description="Imported repositories across the platform."
      />
      <div className="mb-4">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search repositories…"
          className="max-w-xs"
        />
      </div>
      <AdminTable
        loading={repos.isLoading}
        error={repos.isError}
        onRetry={() => repos.refetch()}
        headers={["Repository", "Owner", "Health", "Dependencies", "Last Scan", "Status"]}
        rows={(repos.data?.items || []).map((r) => [
          r.full_name,
          r.owner_email || "—",
          r.health_score != null ? String(r.health_score) : "—",
          String(r.dependency_count),
          r.last_scan_at ? new Date(r.last_scan_at).toLocaleDateString() : "—",
          r.is_archived ? "archived" : r.sync_status,
        ])}
      />
    </>
  );
}
