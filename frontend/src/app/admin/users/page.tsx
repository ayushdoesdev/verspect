"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AdminUserRow } from "@/types";

export default function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AdminUserRow | null>(null);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    p.set("page", String(page));
    p.set("page_size", "25");
    return `?${p.toString()}`;
  }, [q, page]);

  const users = useQuery({
    queryKey: ["admin", "users", params],
    queryFn: () => api.adminUsers(params),
  });

  const filtered = useMemo(() => {
    const items = users.data?.items || [];
    if (!status) return items;
    return items.filter((u) => u.status === status);
  }, [users.data?.items, status]);

  return (
    <>
      <AdminPageHeader
        title="Users"
        description="All platform accounts across organizations."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Search name or email…"
          className="max-w-xs"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <AdminTable
          loading={users.isLoading}
          error={users.isError}
          onRetry={() => users.refetch()}
          headers={[
            "Name",
            "Email",
            "Provider",
            "Verified",
            "Plan",
            "Organization",
            "Repositories",
            "Created",
            "Last Login",
            "Status",
          ]}
          rows={filtered.map((u) => [
            u.name || "—",
            u.email,
            u.github_connected ? "GitHub" : "Email",
            u.verified ? "Yes" : "No",
            u.plan,
            "—",
            String(u.repositories ?? 0),
            new Date(u.created_at).toLocaleDateString(),
            u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : "—",
            u.status,
          ])}
          onRowClick={(i) => setSelected(filtered[i] || null)}
        />

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">User details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {!selected ? (
              <p className="text-muted-foreground">Select a user to view details.</p>
            ) : (
              <>
                <div className="font-medium">{selected.name || "—"}</div>
                <div className="text-muted-foreground">{selected.email}</div>
                <div>Provider: {selected.github_connected ? "GitHub" : "Email"}</div>
                <div>Verified: {selected.verified ? "Yes" : "No"}</div>
                <div>Plan: {selected.plan}</div>
                <div>Repositories: {selected.repositories}</div>
                <div>Status: {selected.status}</div>
                <div>Admin: {selected.is_admin ? "Yes" : "No"}</div>
                <div className="text-xs text-muted-foreground">
                  Created {new Date(selected.created_at).toLocaleString()}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Previous
        </Button>
        <span className="text-xs text-muted-foreground">
          Page {page}
          {users.data?.total != null ? ` · ${users.data.total} total` : ""}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={!users.data?.has_next}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </Button>
      </div>
    </>
  );
}
