"use client";

import { AdminPageHeader } from "@/components/layout/admin-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminSettingsPage() {
  return (
    <>
      <AdminPageHeader
        title="Settings"
        description="Platform console preferences. Product billing and entitlements stay in the customer app."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Access</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>Platform Admin requires `is_admin=true` on the user record.</p>
            <p>Sign in only via `/admin/login`. Customer accounts cannot enter this console.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Bootstrap admin</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              In development/beta, a bootstrap admin may be created on startup when none exists
              (`admin@verspect.dev`).
            </p>
            <p>Never enabled automatically in production.</p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
