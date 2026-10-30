"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type Entitlements = {
  plan: string;
  status: string;
  trialEndsAt?: string | null;
  trialActive: boolean;
  evaluationActive: boolean;
  evaluationExpired: boolean;
  readOnly: boolean;
  canWrite: boolean;
  canImportRepositories: boolean;
  canTriggerScans: boolean;
  canSyncRepositories: boolean;
  canRunBackgroundJobs: boolean;
  /** Active evaluation or paid: Upgrade Simulator (analysis only) */
  upgradeSimulator: boolean;
  /** Pro+: AI Upgrade Advisor & summaries */
  aiEnabled: boolean;
  /** Team/Enterprise: AI Migration Assistant (code generation) */
  aiMigrationAssistant: boolean;
  canGenerateAiMigration: boolean;
  aiMigrationRequestsThisMonth: number;
  apiAccess: boolean;
  scheduledScans: boolean;
  teamsEnabled: boolean;
  loading: boolean;
};

const LOCKED: Omit<Entitlements, "loading"> = {
  plan: "free",
  status: "unknown",
  trialEndsAt: null,
  trialActive: false,
  evaluationActive: false,
  evaluationExpired: true,
  readOnly: true,
  canWrite: false,
  canImportRepositories: false,
  canTriggerScans: false,
  canSyncRepositories: false,
  canRunBackgroundJobs: false,
  upgradeSimulator: false,
  aiEnabled: false,
  aiMigrationAssistant: false,
  canGenerateAiMigration: false,
  aiMigrationRequestsThisMonth: 0,
  apiAccess: false,
  scheduledScans: false,
  teamsEnabled: false,
};

export function useEntitlements(): Entitlements {
  const auth = useAuth();
  const sub = useQuery({
    queryKey: ["subscription"],
    queryFn: api.subscription,
    enabled: auth.isAuthenticated,
    staleTime: 30_000,
  });

  return useMemo(() => {
    const loading = auth.isLoading || (auth.isAuthenticated && sub.isLoading);
    // Fail closed: while loading or on error/missing payload, lock write/AI features.
    if (!auth.isAuthenticated || loading || sub.isError || !sub.data) {
      return { ...LOCKED, loading };
    }

    const data = sub.data;
    const limits = (data.limits || {}) as Record<string, unknown>;

    const evaluationExpired = Boolean(
      data.evaluation_expired ?? limits.evaluation_expired,
    );
    const evaluationActive = Boolean(
      data.evaluation_active ?? (data.plan === "free" && !evaluationExpired),
    );
    const canWrite = Boolean(data.can_write ?? limits.can_write ?? !evaluationExpired);
    const readOnly = Boolean(data.read_only ?? limits.read_only ?? !canWrite);

    const upgradeSimulator = Boolean(
      data.upgrade_simulator ?? limits.upgrade_simulator ?? canWrite,
    );
    const aiEnabled = Boolean(data.ai_enabled ?? limits.ai_enabled);
    const canMigration = Boolean(
      data.can_generate_ai_migration ??
        data.ai_migration_assistant ??
        limits.ai_migration_assistant,
    );

    return {
      plan: data.plan || "free",
      status: data.status || "active",
      trialEndsAt: data.trial_ends_at,
      trialActive: Boolean(data.trial_active ?? evaluationActive),
      evaluationActive,
      evaluationExpired,
      readOnly,
      canWrite,
      canImportRepositories: Boolean(data.can_import_repositories ?? canWrite),
      canTriggerScans: Boolean(data.can_trigger_scans ?? canWrite),
      canSyncRepositories: Boolean(data.can_sync_repositories ?? canWrite),
      canRunBackgroundJobs: Boolean(data.can_run_background_jobs ?? canWrite),
      upgradeSimulator,
      aiEnabled,
      aiMigrationAssistant: canMigration,
      canGenerateAiMigration: canMigration,
      aiMigrationRequestsThisMonth: data.ai_migration_requests_this_month ?? 0,
      apiAccess: Boolean(limits.api_access),
      scheduledScans: Boolean(limits.scheduled_scans),
      teamsEnabled: Boolean(limits.teams_enabled),
      loading: false,
    };
  }, [auth.isAuthenticated, auth.isLoading, sub.data, sub.isError, sub.isLoading]);
}
