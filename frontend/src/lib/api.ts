const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const IS_DEV = process.env.NODE_ENV === "development";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function authLog(...args: unknown[]) {
  if (IS_DEV && typeof window !== "undefined") {
    console.log("[auth]", ...args);
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function setTokens(access: string, refresh: string, opts?: { silent?: boolean }) {
  if (typeof window === "undefined") return;
  if (!access || !refresh) {
    authLog("setTokens skipped — missing access or refresh", {
      hasAccess: !!access,
      hasRefresh: !!refresh,
    });
    return;
  }
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
  // Soft cookie for middleware awareness (not httpOnly — SPA bearer auth remains primary)
  try {
    const maxAge = 60 * 60 * 24 * 30;
    document.cookie = `access_token=${encodeURIComponent(access)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
  } catch {
    /* ignore */
  }
  authLog("token saved", {
    access: `${access.slice(0, 12)}…`,
    refresh: `${refresh.slice(0, 12)}…`,
    silent: !!opts?.silent,
  });
  if (!opts?.silent) {
    window.dispatchEvent(new CustomEvent("depintel:tokens-changed"));
  }
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  try {
    document.cookie = "access_token=; Path=/; Max-Age=0; SameSite=Lax";
  } catch {
    /* ignore */
  }
  authLog("tokens cleared");
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("depintel:tokens-cleared"));
  }
}

/** Best-effort server logout (revokes refresh token) before clearing local session. */
export async function logoutRemote(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await apiFetch<{ message: string }>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
    }
  } catch {
    /* local clear still proceeds */
  }
}

export function hasStoredSession(): boolean {
  if (typeof window === "undefined") return false;
  return !!(localStorage.getItem("access_token") || localStorage.getItem("refresh_token"));
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh = getRefreshToken();
    if (!refresh) {
      authLog("refresh skipped — no refresh token");
      return false;
    }
    authLog("refreshing access token…");
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ refresh_token: refresh }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        authLog("refresh failed", res.status, data);
        return false;
      }
      if (!data.access_token || !data.refresh_token) {
        authLog("refresh response missing tokens", data);
        return false;
      }
      setTokens(data.access_token, data.refresh_token);
      authLog("refresh succeeded");
      return true;
    } catch (err) {
      authLog("refresh error", err);
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

function parseErrorDetail(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ") || fallback;
  }
  if (detail && typeof detail === "object") {
    return (
      (detail as { message?: string }).message ||
      JSON.stringify(detail)
    );
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  _retried = false,
): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
    authLog("Authorization header attached", path);
  } else {
    authLog("no access token for request", path);
  }

  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const data = await res.json().catch(() => ({}));

  if (path === "/auth/me") {
    authLog("/auth/me response", res.status, data);
  }

  if (!res.ok) {
    const detail = parseErrorDetail(data, res.statusText);

    // Only attempt refresh / clear when we actually sent a Bearer token
    if (res.status === 401 && token && !_retried && !path.startsWith("/auth/refresh")) {
      authLog("401 with bearer — attempting refresh", path);
      const ok = await refreshAccessToken();
      if (ok) {
        return apiFetch<T>(path, options, true);
      }
      // Refresh failed — now it is safe to clear and treat as logged out
      authLog("refresh failed after 401 — clearing session", path);
      clearTokens();
      throw new ApiError(401, detail || "Session expired");
    }

    // 401 without a sent token: unauthenticated probe — do NOT clear storage
    if (res.status === 401 && !token) {
      authLog("401 without bearer — leaving stored tokens untouched", path);
      throw new ApiError(401, detail || "Not authenticated");
    }

    throw new ApiError(res.status, detail || "Request failed");
  }
  return data as T;
}

export const api = {
  getAuthUrl: () => apiFetch<{ authorization_url: string; state: string }>("/auth/github/url"),
  getGoogleAuthUrl: () =>
    apiFetch<{ authorization_url: string; state: string }>("/auth/google/url"),
  /** Exchange one-time OAuth login ticket (from /login/callback?code=…) for JWTs. */
  exchangeOAuthCode: (code: string) =>
    apiFetch<{
      access_token: string;
      refresh_token: string;
      user: import("@/types").User;
    }>("/auth/oauth/exchange", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  register: async (body: { email: string; password: string; name?: string }) => {
    const data = await apiFetch<{
      access_token: string;
      refresh_token: string;
      user: import("@/types").User;
    }>("/auth/register", { method: "POST", body: JSON.stringify(body) });
    authLog("register response", {
      hasAccess: !!data.access_token,
      hasRefresh: !!data.refresh_token,
      user: data.user?.github_login || data.user?.email,
    });
    return data;
  },
  login: async (body: { email: string; password: string; remember_me?: boolean }) => {
    const data = await apiFetch<{
      access_token: string;
      refresh_token: string;
      user: import("@/types").User;
    }>("/auth/login", { method: "POST", body: JSON.stringify(body) });
    authLog("login response", {
      hasAccess: !!data.access_token,
      hasRefresh: !!data.refresh_token,
      tokenType: (data as { token_type?: string }).token_type,
      expiresIn: (data as { expires_in?: number }).expires_in,
      user: data.user?.github_login || data.user?.email,
    });
    return data;
  },
  forgotPassword: (email: string) =>
    apiFetch<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  me: () => apiFetch<import("@/types").User>("/auth/me"),
  organizations: () => apiFetch<import("@/types").Organization[]>("/organizations"),
  currentOrganization: () => apiFetch<import("@/types").Organization>("/organizations/current"),
  switchOrganization: async (organization_id: string) => {
    const org = await apiFetch<import("@/types").Organization>("/organizations/switch", {
      method: "POST",
      body: JSON.stringify({ organization_id }),
    });
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("depintel:org-switched", { detail: org }));
    }
    return org;
  },
  orgMembers: (orgId: string) =>
    apiFetch<import("@/types").OrgMember[]>(`/organizations/${orgId}/members`),
  inviteMember: (orgId: string, body: { email: string; role: string }) =>
    apiFetch<import("@/types").Invitation>(`/organizations/${orgId}/invitations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  removeMember: (orgId: string, userId: string) =>
    apiFetch<{ message: string }>(`/organizations/${orgId}/members/${userId}`, {
      method: "DELETE",
    }),
  pricing: () =>
    apiFetch<{
      plans: Array<Record<string, unknown>>;
      feature_comparison?: Array<Record<string, unknown>>;
      billing_provider?: string;
      publishable_key?: string;
      stripe_publishable_key?: string;
    }>("/billing/pricing"),
  subscription: () => apiFetch<import("@/types").SubscriptionInfo>("/billing/subscription"),
  usage: () => apiFetch<import("@/types").UsageInfo>("/billing/usage"),
  aiHealth: async () => {
    const base = API_URL.replace(/\/$/, "");
    // Prefer canonical /api/ai/health; fall back to v1
    try {
      const res = await fetch(`${base}/api/ai/health`, { credentials: "include" });
      if (res.ok) return (await res.json()) as import("@/types").AIHealth;
    } catch {
      /* fall through */
    }
    return apiFetch<import("@/types").AIHealth>("/ai/health");
  },
  aiSettings: () => apiFetch<import("@/types").AISettings>("/ai/settings"),
  aiChat: (body: {
    message: string;
    system?: string;
    history?: Array<{ role: string; content: string }>;
    repository_id?: string;
  }) =>
    apiFetch<import("@/types").AIChatResponse>("/ai/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  checkout: (body: { plan: string; interval: string }) =>
    apiFetch<{ url: string; session_id: string; mode: string }>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  changePlan: (body: { plan: string; interval?: string }) =>
    apiFetch<import("@/types").LifecycleActionResult>("/billing/change-plan", {
      method: "POST",
      body: JSON.stringify({ interval: "month", ...body }),
    }),
  cancelSubscription: () =>
    apiFetch<import("@/types").LifecycleActionResult>("/billing/cancel", {
      method: "POST",
    }),
  reactivateSubscription: () =>
    apiFetch<import("@/types").LifecycleActionResult>("/billing/reactivate", {
      method: "POST",
    }),
  clearPendingPlanChange: () =>
    apiFetch<import("@/types").LifecycleActionResult>("/billing/clear-pending", {
      method: "POST",
    }),
  billingPortal: () =>
    apiFetch<{ url: string; mode: string }>("/billing/portal", { method: "POST" }),
  invoices: () => apiFetch<import("@/types").InvoiceInfo[]>("/billing/invoices"),
  dashboard: () => apiFetch<import("@/types").DashboardData>("/dashboard"),
  repositories: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").Repository>>(`/repositories${params}`),
  /** lifecycle: all | active | archived (default active when omitted server-side) */
  listRepositories: (opts?: {
    page?: number;
    page_size?: number;
    lifecycle?: "all" | "active" | "archived";
    search?: string;
  }) => {
    const sp = new URLSearchParams();
    sp.set("page", String(opts?.page ?? 1));
    sp.set("page_size", String(opts?.page_size ?? 50));
    if (opts?.lifecycle) sp.set("lifecycle", opts.lifecycle);
    if (opts?.search) sp.set("search", opts.search);
    return apiFetch<import("@/types").Paginated<import("@/types").Repository>>(
      `/repositories?${sp.toString()}`,
    );
  },
  repository: (id: string) =>
    apiFetch<import("@/types").Repository>(`/repositories/${id}`),
  githubRepos: () =>
    apiFetch<import("@/types").GitHubRepo[]>("/repositories/github"),
  importRepos: (github_repo_ids: number[]) =>
    apiFetch<import("@/types").Repository[]>("/repositories/import", {
      method: "POST",
      body: JSON.stringify({
        github_repo_ids,
        install_webhooks: true,
        trigger_scan: true,
      }),
    }),
  deleteRepository: async (id: string) => {
    const result = await apiFetch<{
      repository_id: string;
      full_name: string;
      github_repository_preserved: boolean;
    }>(`/repositories/${id}`, { method: "DELETE" });
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("depintel:repository-deleted", { detail: { repositoryId: id } }),
      );
    }
    return result;
  },
  archiveRepository: (id: string) =>
    apiFetch<import("@/types").Repository>(`/repositories/${id}/archive`, {
      method: "POST",
    }),
  unarchiveRepository: (id: string) =>
    apiFetch<import("@/types").Repository>(`/repositories/${id}/unarchive`, {
      method: "POST",
    }),
  pauseRepositorySync: (id: string) =>
    apiFetch<import("@/types").Repository>(`/repositories/${id}/pause-sync`, {
      method: "POST",
    }),
  resumeRepositorySync: (id: string) =>
    apiFetch<import("@/types").Repository>(`/repositories/${id}/resume-sync`, {
      method: "POST",
    }),
  updateRepository: (id: string, body: { is_watching?: boolean; is_archived?: boolean }) =>
    apiFetch<import("@/types").Repository>(`/repositories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  dependencies: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").Dependency>>(`/dependencies${params}`),
  dependency: (id: string) =>
    apiFetch<import("@/types").DependencyDetail>(`/dependencies/${id}`),
  refreshAi: (id: string) =>
    apiFetch<import("@/types").Dependency>(`/dependencies/${id}/ai/refresh`, {
      method: "POST",
    }),
  alerts: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").Alert>>(`/alerts${params}`),
  updateAlert: (id: string, status: string) =>
    apiFetch<import("@/types").Alert>(`/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  triggerScan: (repositoryId: string, opts: { force?: boolean } = {}) =>
    apiFetch<import("@/types").Scan>(
      `/scans/repositories/${repositoryId}${opts.force ? "?force=true" : ""}`,
      {
        method: "POST",
        body: JSON.stringify({ scan_type: "manual" }),
      },
    ),
  cancelScan: (scanId: string) =>
    apiFetch<import("@/types").Scan>(`/scans/${scanId}/cancel`, {
      method: "POST",
    }),
  retryScan: (scanId: string) =>
    apiFetch<import("@/types").Scan>(`/scans/${scanId}/retry`, {
      method: "POST",
    }),
  getWorkerStatus: () => apiFetch<import("@/types").WorkerStatus>("/scans/worker-status"),
  scans: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").Scan>>(`/scans${params}`),
  getScan: (scanId: string) =>
    apiFetch<import("@/types").Scan>(`/scans/${scanId}`),
  search: (q: string) =>
    apiFetch<{ query: string; total: number; hits: import("@/types").SearchHit[] }>(
      `/search?q=${encodeURIComponent(q)}`,
    ),
  updateSettings: (body: Partial<import("@/types").User>) =>
    apiFetch<import("@/types").User>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  simulateUpgrade: (
    dependencyId: string,
    body?: { target_version?: string; force_refresh?: boolean },
  ) =>
    apiFetch<import("@/types").UpgradeSimulation>(
      `/dependencies/${dependencyId}/simulate-upgrade`,
      {
        method: "POST",
        body: JSON.stringify(body || {}),
      },
    ),
  analyzeUpgradeImpact: (
    dependencyId: string,
    body?: { target_version?: string },
  ) =>
    apiFetch<import("@/types").UpgradeImpactReport>(
      `/dependencies/${dependencyId}/analyze-upgrade-impact`,
      {
        method: "POST",
        body: JSON.stringify(body || {}),
      },
    ),
  repositoryDependencyGraph: (repositoryId: string) =>
    apiFetch<import("@/types").DependencyGraphResponse>(
      `/repositories/${repositoryId}/dependency-graph`,
    ),
  getLicensePolicy: (orgId: string) =>
    apiFetch<import("@/types").LicensePolicy>(
      `/organizations/${orgId}/license-policy`,
    ),
  updateLicensePolicy: (
    orgId: string,
    body: { reject?: string[]; warn?: string[] },
  ) =>
    apiFetch<import("@/types").LicensePolicy>(
      `/organizations/${orgId}/license-policy`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  createMigrationPullRequest: (
    simulationId: string,
    body: { confirm: boolean },
  ) =>
    apiFetch<{
      pull_request_url?: string;
      branch: string;
      applied_files: string[];
      skipped: string[];
      number?: number;
    }>(`/migration/simulations/${simulationId}/pull-request`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSimulations: (dependencyId: string) =>
    apiFetch<import("@/types").UpgradeSimulation[]>(
      `/dependencies/${dependencyId}/simulations`,
    ),
  getSimulation: (dependencyId: string, simulationId: string) =>
    apiFetch<import("@/types").UpgradeSimulation>(
      `/dependencies/${dependencyId}/simulations/${simulationId}`,
    ),
  refreshSimulation: (dependencyId: string, simulationId: string) =>
    apiFetch<import("@/types").UpgradeSimulation>(
      `/dependencies/${dependencyId}/simulations/${simulationId}/refresh`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  cancelSimulation: (dependencyId: string, simulationId: string) =>
    apiFetch<import("@/types").UpgradeSimulation>(
      `/dependencies/${dependencyId}/simulations/${simulationId}/cancel`,
      { method: "POST" },
    ),
  retrySimulation: (dependencyId: string, simulationId: string) =>
    apiFetch<import("@/types").UpgradeSimulation>(
      `/dependencies/${dependencyId}/simulations/${simulationId}/retry`,
      { method: "POST" },
    ),
  migrationRules: (params = "") =>
    apiFetch<import("@/types").MigrationRule[]>(`/migration/rules${params}`),
  knowledgeBaseLookup: (packageName: string, params = "") =>
    apiFetch<{
      entry: unknown;
      rules: import("@/types").MigrationRule[];
      release_notes_count: number;
      documentation_sources: Array<{
        source_type: string;
        url: string;
        title?: string | null;
      }>;
    }>(`/migration/knowledge-base/${encodeURIComponent(packageName)}${params}`),

  submitFeedback: (body: {
    category: string;
    title: string;
    description: string;
    email: string;
    repository?: string;
    priority?: string;
    page_url?: string;
    app_version?: string;
    browser?: string;
  }) =>
    apiFetch<import("@/types").FeedbackSubmission>("/feedback", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  submitContactRequest: (body: {
    name: string;
    company?: string;
    email: string;
    team_size?: string;
    message: string;
  }) =>
    apiFetch<import("@/types").ContactRequest>("/contact", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  adminOverview: () => apiFetch<import("@/types").AdminOverview>("/admin/overview"),
  adminAnalytics: (days = 14) =>
    apiFetch<import("@/types").AdminAnalytics>(`/admin/analytics?days=${days}`),
  adminUsers: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").AdminUserRow>>(
      `/admin/users${params}`,
    ),
  adminOrganizations: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").AdminOrgRow>>(
      `/admin/organizations${params}`,
    ),
  adminRepositories: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").AdminRepoRow>>(
      `/admin/repositories${params}`,
    ),
  adminFeedback: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").FeedbackSubmission>>(
      `/admin/feedback${params}`,
    ),
  adminFeedbackDetail: (id: string) =>
    apiFetch<import("@/types").FeedbackSubmission>(`/admin/feedback/${id}`),
  adminUpdateFeedbackStatus: (id: string, status: string) =>
    apiFetch<import("@/types").FeedbackSubmission>(`/admin/feedback/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  adminContactRequests: (params = "") =>
    apiFetch<import("@/types").Paginated<import("@/types").ContactRequest>>(
      `/admin/contact-requests${params}`,
    ),
};
