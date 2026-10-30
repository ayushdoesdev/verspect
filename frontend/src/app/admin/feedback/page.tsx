"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function notesKey(id: string) {
  return `verspect-admin-feedback-notes:${id}`;
}

export default function AdminFeedbackPage() {
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const qc = useQueryClient();

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (statusFilter) p.set("status", statusFilter);
    const s = p.toString();
    return s ? `?${s}` : "";
  }, [q, statusFilter]);

  const feedback = useQuery({
    queryKey: ["admin", "feedback", params],
    queryFn: () => api.adminFeedback(params),
  });
  const detail = useQuery({
    queryKey: ["admin", "feedback", selectedId],
    queryFn: () => api.adminFeedbackDetail(selectedId!),
    enabled: !!selectedId,
  });
  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.adminUpdateFeedbackStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "feedback"] }),
  });

  useEffect(() => {
    if (!selectedId) {
      setNotes("");
      return;
    }
    setNotes(sessionStorage.getItem(notesKey(selectedId)) || "");
  }, [selectedId]);

  return (
    <>
      <AdminPageHeader title="Feedback" description="Every Private Beta submission." />
      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search…"
          className="max-w-xs"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In Progress</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <AdminTable
          loading={feedback.isLoading}
          error={feedback.isError}
          onRetry={() => feedback.refetch()}
          headers={["Category", "Priority", "Status", "Title", "User", "Email", "Created"]}
          rows={(feedback.data?.items || []).map((f) => [
            f.category,
            f.priority || "medium",
            f.status,
            f.title,
            f.user_id ? "Account" : "Guest",
            f.email,
            new Date(f.created_at).toLocaleString(),
          ])}
          onRowClick={(i) => {
            const item = feedback.data?.items?.[i];
            if (item) setSelectedId(item.id);
          }}
        />

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {!selectedId ? (
              <p className="text-muted-foreground">Select a submission.</p>
            ) : detail.isLoading ? (
              <p className="text-muted-foreground">Loading…</p>
            ) : detail.data ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <Badge>{detail.data.category}</Badge>
                  <Badge>{detail.data.priority || "medium"}</Badge>
                  <Badge>{detail.data.status}</Badge>
                </div>
                <div className="font-medium">{detail.data.title}</div>
                <p className="whitespace-pre-wrap text-muted-foreground">
                  {detail.data.description}
                </p>
                  <div className="space-y-1 text-xs text-muted-foreground">
                  <div>{detail.data.email}</div>
                  {detail.data.repository ? <div>Repository: {detail.data.repository}</div> : null}
                  {detail.data.browser ? (
                    <div className="truncate">Browser: {detail.data.browser}</div>
                  ) : null}
                  {detail.data.page_url ? (
                    <div className="truncate">Page: {detail.data.page_url}</div>
                  ) : null}
                  {detail.data.app_version ? (
                    <div>App Version: {detail.data.app_version}</div>
                  ) : null}
                </div>

                <div className="space-y-1.5 pt-1">
                  <label className="text-xs font-medium text-muted-foreground">Status</label>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={detail.data.status}
                    disabled={updateStatus.isPending}
                    onChange={(e) =>
                      updateStatus.mutate({ id: detail.data!.id, status: e.target.value })
                    }
                  >
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Internal notes
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => {
                      setNotes(e.target.value);
                      if (selectedId) {
                        sessionStorage.setItem(notesKey(selectedId), e.target.value);
                      }
                    }}
                    rows={4}
                    placeholder="Private triage notes for this session…"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">Not found.</p>
            )}
            {selectedId ? (
              <Button size="sm" variant="ghost" onClick={() => setSelectedId(null)}>
                Clear selection
              </Button>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
