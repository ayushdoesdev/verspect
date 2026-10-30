export type User = {
  id: string;
  github_id?: number | null;
  github_login: string;
  email?: string | null;
  name?: string | null;
  avatar_url?: string | null;
  auth_provider?: string;
  email_verified?: boolean;
  is_active: boolean;
  is_admin: boolean;
  onboarding_completed?: boolean;
  active_organization_id?: string | null;
  email_notifications: boolean;
  slack_notifications: boolean;
  slack_webhook_url?: string | null;
  notify_on_critical_cve: boolean;
  notify_on_major_release: boolean;
  notify_on_license_violation: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_personal: boolean;
  owner_user_id: string;
  role?: string | null;
  description?: string | null;
  license_policy?: {
    reject: string[];
    warn: string[];
    source: string;
  } | null;
  created_at: string;
  updated_at: string;
};

export type OrgMember = {
  id: string;
  user_id: string;
  role: string;
  email?: string | null;
  name?: string | null;
  github_login?: string | null;
  avatar_url?: string | null;
  joined_at?: string | null;
};

export type Invitation = {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  token?: string | null;
};

export type SubscriptionInfo = {
  plan: string;
  status: string;
  billing_interval: string;
  seat_count: number;
  trial_ends_at?: string | null;
  trial_active?: boolean;
  evaluation_active?: boolean;
  evaluation_expired?: boolean;
  read_only?: boolean;
  can_write?: boolean;
  can_import_repositories?: boolean;
  can_trigger_scans?: boolean;
  can_sync_repositories?: boolean;
  can_run_background_jobs?: boolean;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  pending_plan?: string | null;
  pending_interval?: string | null;
  pending_change_type?: string | null;
  pending_change_effective_at?: string | null;
  pending_change_message?: string | null;
  can_upgrade?: boolean;
  can_downgrade?: boolean;
  can_cancel?: boolean;
  can_reactivate?: boolean;
  billing_provider?: string | null;
  next_invoice_at?: string | null;
  price_monthly?: number | null;
  price_label?: string | null;
  upgrade_simulator?: boolean;
  ai_enabled?: boolean;
  ai_migration_assistant?: boolean;
  can_generate_ai_migration?: boolean;
  can_view_ai_migration_reports?: boolean;
  ai_migration_requests_this_month?: number;
  ai_migration_tokens_this_month?: number;
  ai_migration_cost_this_month?: number;
  limits: Record<string, unknown>;
};

export type LifecycleActionResult = {
  action: string;
  plan: string;
  pending_plan?: string | null;
  pending_change_type?: string | null;
  pending_change_effective_at?: string | null;
  cancel_at_period_end: boolean;
  current_period_end?: string | null;
  message: string;
  checkout_url?: string | null;
  mode?: string;
  provider?: string | null;
  soft_limit_summary?: Record<string, unknown> | null;
};

export type UsageInfo = {
  plan: string;
  repositories_used: number;
  repositories_limit: number | null;
  members_used: number;
  members_limit: number | null;
  monthly_scan_limit?: number | null;
  monthly_scans_used?: number;
  evaluation_active?: boolean;
  evaluation_expired?: boolean;
  read_only?: boolean;
  can_write?: boolean;
  upgrade_simulator?: boolean;
  ai_enabled: boolean;
  ai_migration_assistant?: boolean;
  can_generate_ai_migration?: boolean;
  ai_migration_requests_this_month?: number;
  ai_migration_tokens_this_month?: number;
  ai_migration_cost_this_month?: number;
  ai_migration_avg_ms?: number;
  teams_enabled: boolean;
  api_access: boolean;
  scheduled_scans: boolean;
  webhooks?: boolean;
  rbac?: boolean;
  audit_logs?: boolean;
};

export type InvoiceInfo = {
  id: string;
  number?: string | null;
  status: string;
  amount_due: number;
  amount_paid: number;
  currency: string;
  hosted_invoice_url?: string | null;
  paid_at?: string | null;
};

export type Repository = {
  id: string;
  owner_id: string;
  github_repo_id: number;
  full_name: string;
  name: string;
  owner_login: string;
  description?: string | null;
  html_url: string;
  clone_url: string;
  default_branch: string;
  language?: string | null;
  detected_language?: string | null;
  detected_language_id?: string | null;
  detected_framework?: string | null;
  package_manager?: string | null;
  support_status?: string | null;
  support_label?: string | null;
  classification?: Record<string, unknown> | null;
  is_private: boolean;
  is_fork: boolean;
  stars_count: number;
  forks_count: number;
  open_issues_count: number;
  is_watching: boolean;
  is_archived?: boolean;
  archived_at?: string | null;
  webhook_active: boolean;
  sync_status: string;
  last_synced_at?: string | null;
  last_commit_sha?: string | null;
  dependency_count: number;
  outdated_count: number;
  vulnerable_count: number;
  critical_alert_count: number;
  warning_count: number;
  health_score?: number | null;
  license_issues_count: number;
  topics?: string[] | null;
  created_at: string;
  updated_at: string;
};

export type Dependency = {
  id: string;
  repository_id: string;
  package_name: string;
  normalized_name: string;
  ecosystem: string;
  manifest_source?: string | null;
  is_direct: boolean;
  is_dev: boolean;
  current_version?: string | null;
  latest_version?: string | null;
  version_constraint?: string | null;
  is_outdated: boolean;
  major_behind: number;
  minor_behind: number;
  patch_behind: number;
  license_spdx?: string | null;
  license_policy_action?: string | null;
  status: string;
  health_score?: number | null;
  risk_score?: number | null;
  usage_count: number;
  file_count: number;
    has_vulnerabilities: boolean;
    vulnerability_count: number;
    critical_vuln_count: number;
    osv_status?: string | null;
  pypi_url?: string | null;
  home_page?: string | null;
  github_repo_url?: string | null;
  summary?: string | null;
  download_count_month?: number | null;
  github_stars?: number | null;
  last_release_at?: string | null;
  ai_explanation?: string | null;
  ai_should_update?: string | null;
  ai_security_summary?: string | null;
  created_at: string;
  updated_at: string;
};

export type LibraryUsage = {
  id: string;
  dependency_id: string;
  package_name: string;
  symbol: string;
  fully_qualified_name: string;
  usage_kind: string;
  file_path: string;
  line: number;
  column: number;
  enclosing_function?: string | null;
  enclosing_class?: string | null;
  code_snippet?: string | null;
};

export type CVE = {
  id: string;
  osv_id: string;
  cve_id?: string | null;
  summary: string;
  severity: string;
  cvss_score?: number | null;
  fixed_version?: string | null;
  is_fixable: boolean;
  package_name: string;
};

export type Release = {
  id: string;
  package_name: string;
  version: string;
  previous_version?: string | null;
  is_major: boolean;
  ai_summary?: string | null;
  breaking_changes?: string[] | null;
  migration_difficulty?: string | null;
  risk_score?: number | null;
  has_breaking_changes: boolean;
  released_at?: string | null;
};

export type Alternative = {
  id: string;
  alternative_name: string;
  reason: string;
  pros?: string[] | null;
  cons?: string[] | null;
  migration_effort: string;
  popularity_score?: number | null;
  health_score?: number | null;
  confidence?: number | null;
  rank: number;
};

export type MigrationReport = {
  id: string;
  title: string;
  summary: string;
  difficulty: string;
  risk_score: number;
  step_by_step?: string[] | null;
  recommendation?: string | null;
  should_update?: boolean | null;
  from_version: string;
  to_version: string;
};

export type DependencyDetail = Dependency & {
  usages: LibraryUsage[];
  cves: CVE[];
  releases: Release[];
  alternatives: Alternative[];
  migration_reports: MigrationReport[];
  upgrade_advisor?: {
    should_i_upgrade: string;
    why: string[];
    benefits: string[];
    risks: string[];
    estimated_effort: string;
    recommended_version?: string | null;
    immediate_action: string;
    confidence: number;
    confidence_label: string;
    confidence_reason: string;
  } | null;
  documentation_links?: Array<{ label: string; url: string }>;
  health_breakdown?: {
    overall?: number | null;
    security?: number;
    maintenance?: number;
    freshness?: number;
    license?: number;
    components?: Record<string, number>;
    weights?: Record<string, number>;
    missing_signals?: string[];
    completeness?: number;
    data_quality?: "unknown" | "partial" | "complete";
  } | null;
  introduced_by?: Array<{
    parent_package: string;
    parent_dependency_id: string;
    relationship: string;
    source?: string | null;
  }>;
};

export type Alert = {
  id: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  recommendation?: string | null;
  repository_id?: string | null;
  dependency_id?: string | null;
  created_at: string;
};

export type Scan = {
  id: string;
  repository_id: string;
  scan_type: string;
  status: string;
  progress_percent: number;
  current_stage?: string | null;
  dependencies_found: number;
  vulnerabilities_found: number;
  error_message?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  created_at: string;
  summary?: Record<string, unknown> | null;
  extra_metadata?: Record<string, unknown> | null;
  // Worker lifecycle / observability
  last_heartbeat_at?: string | null;
  worker_name?: string | null;
  retry_count?: number;
  cancel_requested?: boolean;
  stage_timings?: StageTiming[] | null;
  queue_position?: number | null;
};

export type StageTiming = {
  stage: string;
  started_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
};

export type WorkerStatus = {
  online: boolean;
  status: "online" | "offline" | "blocked";
  active_workers: number;
  workers: string[];
  active_tasks: number;
  reserved_tasks: number;
  queue_depths: Record<string, number>;
  queued_total: number;
  queue_blocked: boolean;
  message: string;
  detail?: string | null;
  heartbeat_seconds: number;
  pickup_timeout_seconds: number;
  stale_timeout_minutes: number;
};

export type DashboardData = {
  stats: {
    repository_count: number;
    dependency_count: number;
    outdated_count: number;
    critical_count: number;
    warning_count: number;
    average_health_score?: number | null;
    vulnerable_count: number;
    license_issue_count: number;
    open_alert_count: number;
    osv_unavailable_count?: number;
  };
  charts: {
    dependency_distribution: { label: string; value: number }[];
    outdated_trend: { label: string; value: number }[];
    health_scores: { label: string; value: number }[];
    severity_breakdown: { label: string; value: number }[];
  };
  latest_releases: Release[];
  critical_cves: CVE[];
  recent_alerts: Alert[];
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
};

export type SearchHit = {
  type: string;
  id: string;
  title: string;
  subtitle?: string | null;
  url: string;
  score: number;
};

export type GitHubRepo = {
  github_repo_id: number;
  full_name: string;
  name: string;
  owner_login: string;
  description?: string | null;
  html_url: string;
  language?: string | null;
  is_private: boolean;
  stars_count: number;
  already_imported: boolean;
};

export type MigrationFindingStatus =
  | "no_migration_required"
  | "automatic_migration"
  | "manual_review_required"
  | "unknown"
  | "unresolved";

export type SuggestedChange = {
  file_path: string;
  line?: number | null;
  symbol?: string | null;
  current_code: string;
  suggested_code?: string | null;
  explanation: string;
  confidence: number;
  automatic: boolean;
  unified_diff?: string | null;
  official_reference?: string | null;
  validation_status?: string | null;
  migration_status?: MigrationFindingStatus | null;
  status_title?: string | null;
  status_detail?: string | null;
  /** AI Migration Assistant enrichment — never overrides migration_status */
  ai_explanation?: string | null;
  ai_suggested_code?: string | null;
  ai_confidence?: number | null;
  reasoning?: string | null;
  migration_notes?: string | null;
  source?: string | null;
  analysis_source?: string | null;
  claim_status?: string | null;
  unknown?: boolean | null;
};

export type FileImpact = {
  file_path: string;
  affected_apis: string[];
  reason: string;
  confidence: number;
  suggested_changes?: string[];
  enclosing_functions?: string[];
  enclosing_classes?: string[];
  usage_sites?: Array<{
    symbol?: string | null;
    fully_qualified_name?: string | null;
    usage_kind?: string | null;
    line?: number | null;
    column?: number | null;
    enclosing_function?: string | null;
    enclosing_class?: string | null;
    code_snippet?: string | null;
  }>;
  rules?: Array<{
    symbol: string;
    kind: string;
    severity: string;
    description: string;
    official_reference?: string | null;
  }>;
};

export type MigrationPhase = {
  phase: number;
  title: string;
  description: string;
  reasoning: string;
  difficulty: string;
  estimated_duration_hours: number;
  tasks: string[];
};

export type BreakingAPI = {
  symbol: string;
  fully_qualified_name?: string;
  api?: string;
  severity?: string;
  reason?: string;
  description?: string;
  replacement?: string | null;
  confidence: number;
  kind?: string | null;
  change_type?: string | null;
  official_reference?: string | null;
  analysis_source?: string | null;
  is_breaking?: boolean;
  affected_files?: string[];
  evidence?: Array<{
    file_path: string;
    line?: number | null;
    code_snippet?: string | null;
    symbol?: string | null;
    fully_qualified_name?: string | null;
  }>;
};

export type UpgradeImpactFinding = {
  dependency: string;
  current_version: string;
  target_version: string;
  change_type: string;
  affected_api: string;
  description: string;
  affected_files: string[];
  evidence: Array<{
    file_path: string;
    line?: number | null;
    code_snippet?: string | null;
    symbol?: string | null;
    fully_qualified_name?: string | null;
  }>;
  confidence: number;
  analysis_source: string;
  official_reference?: string | null;
  before?: string | null;
  after?: string | null;
  severity?: string | null;
  is_breaking: boolean;
};

export type UpgradeImpactReport = {
  package_name: string;
  normalized_name: string;
  current_version: string;
  target_version: string;
  analysis_source: string;
  catalog_rules_applied: number;
  usage_sites: number;
  used_apis: string[];
  findings: UpgradeImpactFinding[];
  breaking_findings: UpgradeImpactFinding[];
  unresolved_apis: string[];
  unchanged_apis: string[];
  affected_files: Array<Record<string, unknown>>;
  official_references: Array<{ title?: string; url?: string; source_type?: string }>;
  analysis_limitations?: string[];
  summary: string;
  confidence: number;
};

export type DependencyGraphResponse = {
  repository_id: string;
  nodes: Array<{
    id: string;
    package_name: string;
    normalized_name: string;
    version?: string | null;
    is_direct: boolean;
    is_outdated: boolean;
    has_vulnerabilities: boolean;
    health_score?: number | null;
    license_spdx?: string | null;
  }>;
  edges: Array<{
    id: string;
    parent_dependency_id: string;
    child_dependency_id: string;
    relationship: string;
    source?: string | null;
  }>;
  node_count: number;
  edge_count: number;
};

export type LicensePolicy = {
  reject: string[];
  warn: string[];
  source: string;
};

export type DeprecatedAPI = {
  symbol: string;
  fully_qualified_name: string;
  reason: string;
  replacement?: string | null;
  removal_version?: string | null;
  confidence: number;
  official_reference?: string | null;
};

export type MigrationRule = {
  id?: string | null;
  library: string;
  from_version: string;
  to_version: string;
  symbol: string;
  kind: string;
  description: string;
  severity: string;
  confidence: number;
  before?: string | null;
  after?: string | null;
  reason?: string | null;
  official_reference?: string | null;
  auto_fixable: boolean;
  estimated_effort: string;
  validation_status?: string | null;
  /** True when the API is compatible across the version range (no code change). */
  unchanged?: boolean | null;
};

export type IntelligenceAffectedLocation = {
  file: string;
  line?: number | null;
  api?: string | null;
  reason?: string;
  confidence?: number;
  analysis_method?: string;
  usage_kind?: "verified" | "probable" | "ai_inferred" | string;
  snippet?: string | null;
};

export type IntelligenceFinding = {
  category: string;
  finding: string;
  explanation?: string;
  affected_files?: IntelligenceAffectedLocation[];
  affected_lines?: number[];
  required_change?: string | null;
  confidence?: number;
  evidence?: Array<{ kind?: string; text?: string; source?: string | null; reliability?: string }>;
  source?: string | null;
  analysis_method?: string;
  status?: string;
};

export type IntelligenceCategory = {
  id: string;
  title: string;
  deterministic_completeness?: string;
  completeness?: string;
  analysis_method?: string;
  claim_status?: string;
  answer?: string;
  findings?: IntelligenceFinding[];
  gaps?: string[];
  ai_invoked?: boolean;
  ai_skipped_reason?: string | null;
};

export type DynamicUpgradeIntelligence = {
  package_name?: string;
  ecosystem?: string;
  from_version?: string;
  to_version?: string;
  breaking_classification?: string;
  analysis_method?: string;
  ai_invoked?: boolean;
  ai_skipped_reason?: string | null;
  plan_allows_ai?: boolean;
  degradation?: string[];
  categories?: Record<string, IntelligenceCategory>;
  affected_files?: IntelligenceAffectedLocation[];
  migration_rules?: Record<string, unknown>[];
  required_changes?: IntelligenceFinding[];
  summary?: string;
  confidence?: number;
  sources?: Array<{ label?: string; url?: string }>;
};

export type UpgradeSimulation = {
  id: string;
  dependency_id: string;
  repository_id: string;
  package_name: string;
  from_version: string;
  to_version: string;
  status: string;
  progress_percent: number;
  current_stage?: string | null;
  // Worker lifecycle / observability
  queued_at?: string | null;
  last_heartbeat_at?: string | null;
  worker_name?: string | null;
  retry_count?: number;
  cancel_requested?: boolean;
  stage_timings?: StageTiming[] | null;
  summary?: string | null;
  safe_to_upgrade?: boolean | null;
  confidence?: number | null;
  readiness_score?: number | null;
  risk_score?: number | null;
  migration_time_hours?: number | null;
  migration_time_label?: string | null;
  breaking_apis?: BreakingAPI[] | null;
  deprecated_apis?: DeprecatedAPI[] | null;
  affected_files?: FileImpact[] | null;
  affected_symbols?: string[] | null;
  affected_functions?: string[] | null;
  affected_classes?: string[] | null;
  security_improvements?: string[] | null;
  performance_improvements?: string[] | null;
  manual_work_required?: string[] | null;
  automatic_fixes_possible?: string[] | null;
  migration_plan?: MigrationPhase[] | null;
  suggested_changes?: SuggestedChange[] | null;
  readiness_factors?: Record<string, number> | null;
  migration_rules?: MigrationRule[] | null;
  official_references?: string[] | null;
  engine_report_id?: string | null;
  collected_sources?: Record<string, unknown> | null;
  dynamic_intelligence?: DynamicUpgradeIntelligence | null;
  breaking_classification?: string | null;
  analysis_method?: string | null;
  ai_invoked?: boolean | null;
  ai_skipped_reason?: string | null;
  model_used?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  created_at: string;
  updated_at: string;
};

export type AIHealth = {
  provider: string;
  model: string;
  available: boolean;
  latency_ms?: number | null;
  status?: string;
  message?: string | null;
  fallbacks?: string[];
};

export type AISettings = {
  configured_provider: string;
  configured_model: string;
  active_provider?: string | null;
  active_model?: string | null;
  available: boolean;
  connection_status?: string | null;
  latency_ms?: number | null;
  health_message?: string | null;
  fallback_providers?: string[];
  supported_providers?: string[];
  ollama_base_url?: string | null;
  ollama_model?: string | null;
};

export type AIChatResponse = {
  reply: string;
  provider: string;
  model: string;
  repository_id?: string | null;
  errors?: string[] | null;
};

export type FeedbackSubmission = {
  id: string;
  category: string;
  title: string;
  description: string;
  email: string;
  repository?: string | null;
  priority?: string;
  has_screenshot?: boolean;
  page_url?: string | null;
  app_version?: string | null;
  browser?: string | null;
  status: string;
  user_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminOverview = {
  total_users: number;
  verified_users: number;
  organizations: number;
  repositories: number;
  repository_scans: number;
  active_scans: number;
  ai_advisor_jobs: number;
  upgrade_simulations: number;
  daily_signups: number;
  daily_imports: number;
  daily_scans: number;
  failed_jobs: number;
  workers: string;
  redis: string;
  database: string;
};

export type AdminAnalytics = {
  daily_users: Array<{ date: string; count: number }>;
  daily_scans: Array<{ date: string; count: number }>;
  daily_simulations: Array<{ date: string; count: number }>;
  ai_advisor_usage: Array<{ date: string; count: number }>;
  failed_jobs: Array<{ date: string; count: number }>;
  average_scan_duration_seconds?: number | null;
  average_simulation_duration_seconds?: number | null;
};

export type AdminUserRow = {
  id: string;
  name?: string | null;
  email: string;
  plan: string;
  verified: boolean;
  github_connected: boolean;
  repositories: number;
  created_at: string;
  last_login_at?: string | null;
  status: string;
  is_admin: boolean;
};

export type ContactRequest = {
  id: string;
  name: string;
  company?: string | null;
  email: string;
  team_size?: string | null;
  message: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type AdminOrgRow = {
  id: string;
  name: string;
  owner_email?: string | null;
  plan: string;
  members: number;
  repository_count: number;
  created_at: string;
};

export type AdminRepoRow = {
  id: string;
  full_name: string;
  owner_email?: string | null;
  health_score?: number | null;
  dependency_count: number;
  last_scan_at?: string | null;
  sync_status: string;
  is_archived: boolean;
};
