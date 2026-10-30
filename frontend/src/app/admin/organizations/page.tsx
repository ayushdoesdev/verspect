"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { Input } from "@/components/ui/input";

export default function AdminOrganizationsPage() {
  const [q, setQ] = useState("");
  const orgs = useQuery({
    queryKey: ["admin", "orgs", q],
    queryFn: () => api.adminOrganizations(q ? `?q=${encodeURIComponent(q)}` : ""),
  });

  return (
    <>
      <AdminPageHeader title="Organizations" description="Customer workspaces and plans." />
      <div className="mb-4">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search organizations…"
          className="max-w-xs"
        />
      </div>
      <AdminTable
        loading={orgs.isLoading}
        error={orgs.isError}
        onRetry={() => orgs.refetch()}
        headers={["Organization", "Plan", "Owner", "Members", "Repositories", "Created"]}
        rows={(orgs.data?.items || []).map((o) => [
          o.name,
          o.plan,
          o.owner_email || "—",
          String(o.members),
          String(o.repository_count),
          new Date(o.created_at).toLocaleDateString(),
        ])}
      />
    </>
  );
}
