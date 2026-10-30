"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { MessageSquarePlus } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FeedbackForm } from "@/components/feedback/feedback-form";

/** Floating feedback button — customer app only (authenticated, not admin console). */
export function FeedbackWidget() {
  const auth = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const onAdmin =
    pathname === "/admin" || pathname.startsWith("/admin/");
  const onMarketingAuthForms =
    pathname === "/login" ||
    pathname === "/signup" ||
    pathname === "/forgot-password" ||
    pathname.startsWith("/login/");

  if (auth.status === "loading" || !auth.isAuthenticated || onAdmin || onMarketingAuthForms) {
    return null;
  }

  return (
    <>
      <Button
        type="button"
        data-testid="feedback-widget-button"
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-[80] shadow-lg"
        size="sm"
      >
        <MessageSquarePlus className="mr-1.5 h-4 w-4" />
        Feedback
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[min(85vh,640px)] w-[calc(100%-2rem)] max-w-[600px] gap-3 overflow-y-auto p-5 sm:rounded-xl">
          <DialogHeader className="space-y-1">
            <DialogTitle className="text-base">Feedback</DialogTitle>
            <DialogDescription className="text-xs">
              Share a bug, idea, or question — we review every submission.
            </DialogDescription>
          </DialogHeader>
          <FeedbackForm
            compact
            onSuccess={() => setTimeout(() => setOpen(false), 900)}
          />
          <div className="border-t border-border pt-3 text-xs text-muted-foreground">
            <span>Need to provide more details? </span>
            <Link
              href="/feedback"
              className="font-medium text-primary hover:underline"
              onClick={() => setOpen(false)}
            >
              Open Feedback Center →
            </Link>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
