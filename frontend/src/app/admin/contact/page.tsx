"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/layout/admin-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ContactRequest } from "@/types";

function notesKey(id: string) {
  return `verspect-admin-contact-notes:${id}`;
}

export default function AdminContactPage() {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<ContactRequest | null>(null);
  const [notes, setNotes] = useState("");

  const contacts = useQuery({
    queryKey: ["admin", "contacts", q],
    queryFn: () => api.adminContactRequests(q ? `?q=${encodeURIComponent(q)}` : ""),
  });

  useEffect(() => {
    if (!selected) {
      setNotes("");
      return;
    }
    setNotes(sessionStorage.getItem(notesKey(selected.id)) || "");
  }, [selected]);

  return (
    <>
      <AdminPageHeader title="Contact Requests" description="Request Demo submissions." />
      <div className="mb-4">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search…"
          className="max-w-xs"
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <AdminTable
          loading={contacts.isLoading}
          error={contacts.isError}
          onRetry={() => contacts.refetch()}
          headers={["Company", "Name", "Email", "Message", "Status", "Created"]}
          rows={(contacts.data?.items || []).map((c) => [
            c.company || "—",
            c.name,
            c.email,
            c.message.slice(0, 80),
            c.status,
            new Date(c.created_at).toLocaleString(),
          ])}
          onRowClick={(i) => setSelected(contacts.data?.items?.[i] || null)}
        />
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Request details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {!selected ? (
              <p className="text-muted-foreground">Select a request.</p>
            ) : (
              <>
                <div className="font-medium">{selected.name}</div>
                <div className="text-muted-foreground">
                  {selected.company || "—"} · {selected.email}
                </div>
                <div>Team size: {selected.team_size || "—"}</div>
                <div>Status: {selected.status}</div>
                <p className="whitespace-pre-wrap text-muted-foreground">{selected.message}</p>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Notes</label>
                  <textarea
                    value={notes}
                    onChange={(e) => {
                      setNotes(e.target.value);
                      sessionStorage.setItem(notesKey(selected.id), e.target.value);
                    }}
                    rows={4}
                    placeholder="Internal follow-up notes…"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
