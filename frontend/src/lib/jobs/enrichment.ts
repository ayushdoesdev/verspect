/** Live enrichment progress surfaced from scan.extra_metadata.enrichment */

export type EnrichmentProgress = {
  package?: string | null;
  index?: number | null;
  total?: number | null;
  phase?: string | null;
};

export type EnrichmentPhase =
  | "versions"
  | "metadata"
  | "vulnerabilities"
  | "health"
  | "alternatives"
  | "persisting"
  | "complete"
  | string;

/** Deterministic worker phases only — never AI / recommendations copy. */
const PHASE_COPY: Record<string, string> = {
  versions: "Checking latest version",
  metadata: "Fetching package metadata",
  vulnerabilities: "Checking security advisories",
  health: "Calculating health score",
  alternatives: "Finding alternative libraries",
  persisting: "Saving dependency intelligence",
  complete: "Dependency Intelligence Complete",
};

/**
 * Fallback rotation when phase has not been published yet.
 * Same deterministic steps only — no stage-title echo, no AI wording.
 */
export const ENRICHMENT_ROTATION: string[] = [
  PHASE_COPY.versions,
  PHASE_COPY.metadata,
  PHASE_COPY.vulnerabilities,
  PHASE_COPY.health,
  PHASE_COPY.alternatives,
  PHASE_COPY.persisting,
];

export function parseEnrichment(
  extraMetadata?: Record<string, unknown> | null,
  summary?: Record<string, unknown> | null,
): EnrichmentProgress | null {
  const fromMeta = (extraMetadata as { enrichment?: EnrichmentProgress } | null | undefined)
    ?.enrichment;
  const fromSummary = (summary as { enrichment?: EnrichmentProgress } | null | undefined)
    ?.enrichment;
  const enrichment = fromMeta || fromSummary;
  if (!enrichment || typeof enrichment !== "object") return null;
  return enrichment;
}

export function enrichmentPhaseCopy(phase?: string | null): string | null {
  if (!phase) return null;
  return PHASE_COPY[phase] || null;
}

export function isEnrichmentStage(stage?: string | null): boolean {
  const s = (stage || "").toLowerCase().replace(/\s+/g, "_");
  return (
    s === "knowledge" ||
    s === "versions" ||
    s === "vulnerabilities" ||
    s === "checking_versions" ||
    s === "checking_vulnerabilities" ||
    s === "checking_licenses"
  );
}

/** e.g. "8 of 14 packages" */
export function enrichmentCountLabel(
  enrichment: EnrichmentProgress | null | undefined,
): string | null {
  const index = enrichment?.index;
  const total = enrichment?.total;
  if (typeof index !== "number" || typeof total !== "number" || total <= 0) return null;
  return `${index} of ${total} packages`;
}
