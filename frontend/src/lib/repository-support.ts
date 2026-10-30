import type { Repository } from "@/types";

const ANALYZABLE = new Set(["fully_supported", "supported"]);

/** UI labels — avoid roadmap marketing wording ("Coming Soon"). */
export function supportStatusLabel(
  repo: Pick<Repository, "support_status" | "support_label">,
): string | null {
  if (repo.support_status === "fully_supported") return "Fully Supported";
  if (repo.support_status === "supported") return "Supported";
  if (repo.support_status === "coming_soon") return "Planned";
  if (repo.support_status === "unknown") return "Not Yet Supported";
  if (repo.support_label === "Coming Soon") return "Planned";
  if (repo.support_label === "Supported") return "Supported";
  return repo.support_label || null;
}

export function isFullySupported(repo: Pick<Repository, "support_status">): boolean {
  return repo.support_status === "fully_supported";
}

/** Analyzer exists — inventory/usage/OSV/license/health can run. */
export function isAnalyzable(repo: Pick<Repository, "support_status">): boolean {
  return ANALYZABLE.has(repo.support_status || "");
}

export function isUnsupported(repo: Pick<Repository, "support_status">): boolean {
  return repo.support_status === "coming_soon" || repo.support_status === "unknown";
}

export function hasPythonUpgradeCatalog(
  repo: Pick<Repository, "detected_language_id">,
): boolean {
  return repo.detected_language_id === "python";
}

export function hasClassification(
  repo: Pick<Repository, "detected_language" | "support_status" | "language">,
): boolean {
  return Boolean(repo.detected_language || repo.support_status || repo.language);
}

export function classificationLanguage(repo: Repository): string {
  return repo.detected_language || repo.language || "Unknown";
}

/** Primary dependency manifest path from classifier evidence, if present. */
export function dependencyManifest(repo: Repository): string | null {
  const evidence = repo.classification?.evidence;
  if (!evidence || typeof evidence !== "object") return null;
  const manifests = (evidence as { manifests?: unknown }).manifests;
  if (!Array.isArray(manifests) || manifests.length === 0) return null;
  const first = manifests.find((m) => typeof m === "string") as string | undefined;
  return first || null;
}

export function classificationConfidence(repo: Repository): number | null {
  const raw = repo.classification?.confidence;
  if (typeof raw !== "number" || Number.isNaN(raw)) return null;
  if (raw <= 1) return Math.round(raw * 100);
  return Math.round(raw);
}

export function supportActionTooltip(repo: Repository, feature: string): string {
  const lang = classificationLanguage(repo);
  if (isAnalyzable(repo)) {
    if (
      (feature === "Upgrade Simulator" || feature === "Upgrade impact") &&
      !hasPythonUpgradeCatalog(repo)
    ) {
      return `${feature} can run. Usage is import/module level; the Python catalog is an extra deterministic source. Missing categories use AI on plans that include it.`;
    }
    return `${feature} is available for this ${lang} repository.`;
  }
  return `${feature} is unavailable until ${lang} has an implemented analyzer.`;
}
