"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArchiveRestore,
  Eye,
  MoreHorizontal,
  Pause,
  Play,
  Trash2,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useJobs } from "@/lib/jobs/jobs-context";
import { useNavRouter } from "@/lib/nav-router";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingButton } from "@/components/loading";
import type { Repository } from "@/types";

type Props = {
  repo: Repository;
  /** Hide "View Details" when already on the detail page. */
  hideViewDetails?: boolean;
};

export function RepositoryActionsMenu({ repo, hideViewDetails }: Props) {
  const qc = useQueryClient();
  const router = useNavRouter();
  const { toast } = useJobs();
  const [removeOpen, setRemoveOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["repositories"] });
    qc.invalidateQueries({ queryKey: ["repository", repo.id] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const pauseMut = useMutation({
    mutationFn: () => api.pauseRepositorySync(repo.id),
    onSuccess: () => {
      invalidate();
      toast("Sync paused", {
        tone: "info",
        description: "Webhook and scheduled syncs are paused. Your GitHub repository is unchanged.",
      });
    },
    onError: (err) => {
      toast("Unable to pause sync", {
        tone: "error",
        description: (err as Error).message,
      });
    },
  });

  const resumeMut = useMutation({
    mutationFn: () => api.resumeRepositorySync(repo.id),
    onSuccess: () => {
      invalidate();
      toast("Sync resumed", {
        tone: "info",
        description: "Verspect will sync this repository again on push and schedule.",
      });
    },
    onError: (err) => {
      toast("Unable to resume sync", {
        tone: "error",
        description: (err as Error).message,
      });
    },
  });

  const archiveMut = useMutation({
    mutationFn: () => api.archiveRepository(repo.id),
    onSuccess: () => {
      setArchiveOpen(false);
      invalidate();
      toast("Repository archived", {
        tone: "info",
        description:
          "Moved to Archived. Historical data is kept. Find it anytime under Repositories → Archived.",
      });
      // Stay on the detail page when already there so the repo remains accessible
      if (!hideViewDetails) {
        router.push("/repositories?lifecycle=archived");
      }
    },
    onError: (err) => {
      toast("Unable to archive", {
        tone: "error",
        description: (err as Error).message,
      });
    },
  });

  const restoreMut = useMutation({
    mutationFn: () => api.unarchiveRepository(repo.id),
    onSuccess: () => {
      invalidate();
      toast("Repository restored", {
        tone: "info",
        description: "Back in the active list. Resume sync when you want updates again.",
      });
    },
    onError: (err) => {
      toast("Unable to restore", {
        tone: "error",
        description: (err as Error).message,
      });
    },
  });

  const removeMut = useMutation({
    mutationFn: () => api.deleteRepository(repo.id),
    onSuccess: () => {
      setRemoveOpen(false);
      invalidate();
      toast("Repository removed", {
        tone: "info",
        description: `${repo.full_name} was removed from Verspect. Your GitHub repository was not deleted.`,
      });
      router.push("/repositories");
    },
    onError: (err) => {
      const detail =
        err instanceof ApiError ? err.detail : (err as Error).message;
      toast("Unable to remove repository", {
        tone: "error",
        description: detail || "Removal failed",
      });
    },
  });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="icon" aria-label="Repository actions">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Repository actions</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {!hideViewDetails ? (
            <DropdownMenuItem onSelect={() => router.push(`/repositories/${repo.id}`)}>
              <Eye className="h-4 w-4" />
              View Details
            </DropdownMenuItem>
          ) : null}
          {!repo.is_archived ? (
            <>
              {repo.is_watching ? (
                <DropdownMenuItem
                  onSelect={() => pauseMut.mutate()}
                  disabled={pauseMut.isPending}
                >
                  <Pause className="h-4 w-4" />
                  Pause Sync
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onSelect={() => resumeMut.mutate()}
                  disabled={resumeMut.isPending}
                >
                  <Play className="h-4 w-4" />
                  Resume Sync
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={() => setArchiveOpen(true)}>
                <Archive className="h-4 w-4" />
                Archive Repository
              </DropdownMenuItem>
            </>
          ) : (
            <DropdownMenuItem
              onSelect={() => restoreMut.mutate()}
              disabled={restoreMut.isPending}
            >
              <ArchiveRestore className="h-4 w-4" />
              Restore Repository
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onSelect={() => setRemoveOpen(true)}
          >
            <Trash2 className="h-4 w-4" />
            {repo.is_archived ? "Remove Permanently" : "Remove Repository"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={archiveOpen} onOpenChange={setArchiveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive {repo.full_name}?</DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-3 text-sm text-muted-foreground">
                <p>
                  Archiving moves this repository to the Archived filter. It stays accessible —
                  you can restore it anytime. Historical Verspect data is preserved.
                </p>
                <ul className="list-disc space-y-1 pl-5">
                  <li>Sync and webhooks pause</li>
                  <li>Active scans are cancelled</li>
                  <li>Scan history, dependencies, findings, and reports remain available (read-only)</li>
                  <li>Your GitHub repository is not modified or deleted</li>
                </ul>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setArchiveOpen(false)}>
              Cancel
            </Button>
            <LoadingButton
              loading={archiveMut.isPending}
              loadingText="Archiving…"
              onClick={() => archiveMut.mutate()}
            >
              Archive
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={removeOpen} onOpenChange={setRemoveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove {repo.full_name} from Verspect?</DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-3 text-sm text-muted-foreground">
                <p>
                  This permanently deletes Verspect data for this repository. It does{" "}
                  <strong className="font-medium text-foreground">not</strong> delete anything on
                  GitHub.
                </p>
                <div>
                  <div className="mb-1 font-medium text-foreground">Will be deleted from Verspect</div>
                  <ul className="list-disc space-y-1 pl-5">
                    <li>Dependency inventory and usage indexes</li>
                    <li>Security findings and alerts</li>
                    <li>Scan history and cached clone</li>
                    <li>Upgrade simulations and AI migration reports</li>
                  </ul>
                </div>
                <div>
                  <div className="mb-1 font-medium text-foreground">Will not be deleted</div>
                  <ul className="list-disc space-y-1 pl-5">
                    <li>The GitHub repository, code, issues, or PRs</li>
                    <li>Your GitHub account or organization</li>
                    <li>Billing subscription or plan entitlement</li>
                  </ul>
                </div>
                <p>Repository quota is released after successful removal. Active scans are cancelled first.</p>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoveOpen(false)}>
              Cancel
            </Button>
            <LoadingButton
              variant="destructive"
              loading={removeMut.isPending}
              loadingText="Removing…"
              onClick={() => removeMut.mutate()}
            >
              Remove from Verspect
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
