import type {
  DecisionType,
  FindingActionType,
  OverallStatus,
  Severity,
  VerificationStatus,
} from "@/lib/api";

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const SEVERITY_BADGE: Record<Severity, string> = {
  high: "border-red-200 bg-red-50 text-red-700",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-sky-200 bg-sky-50 text-sky-700",
  info: "border-slate-200 bg-slate-50 text-slate-600",
};

export const SEVERITY_BORDER: Record<Severity, string> = {
  high: "border-l-red-500",
  medium: "border-l-amber-500",
  low: "border-l-sky-500",
  info: "border-l-slate-400",
};

export const SEVERITY_BOX: Record<Severity, string> = {
  high: "border-red-500 bg-red-500/15 hover:bg-red-500/25",
  medium: "border-amber-500 bg-amber-500/15 hover:bg-amber-500/25",
  low: "border-sky-500 bg-sky-500/15 hover:bg-sky-500/25",
  info: "border-slate-500 bg-slate-500/15 hover:bg-slate-500/25",
};

export const OVERALL_LABEL: Record<OverallStatus, string> = {
  flagged: "Flagged",
  manual_review_required: "Manual review",
  no_issues: "No issues",
};

export const OVERALL_BADGE: Record<OverallStatus, string> = {
  flagged: "border-red-200 bg-red-50 text-red-700",
  manual_review_required: "border-amber-200 bg-amber-50 text-amber-800",
  no_issues: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

export const VERIFICATION_LABEL: Record<VerificationStatus, string> = {
  verified: "Source verified",
  mismatch_detected: "Source mismatch",
  expired: "Expired",
  verification_pending: "Verification pending",
  source_unavailable: "Source unavailable",
  manual_review_required: "Manual review required",
};

export const DECISION_LABEL: Record<DecisionType, string> = {
  approve: "Approve",
  approve_with_deficiencies: "Approve with deficiencies",
  request_rectification: "Request rectification",
  site_inspection: "Send for site inspection",
  reject: "Reject",
};

export const DECISION_DESCRIPTION: Record<DecisionType, string> = {
  approve: "Application meets the reviewed requirements.",
  approve_with_deficiencies: "Approve while listing deficiencies for follow-up.",
  request_rectification: "Send the deficiencies back to the institute.",
  site_inspection: "A site visit is needed before a final decision.",
  reject: "Reject the application. A reason is required.",
};

export const DECISION_BADGE: Record<DecisionType, string> = {
  approve: "border-emerald-200 bg-emerald-50 text-emerald-700",
  approve_with_deficiencies: "border-teal-200 bg-teal-50 text-teal-700",
  request_rectification: "border-amber-200 bg-amber-50 text-amber-800",
  site_inspection: "border-violet-200 bg-violet-50 text-violet-700",
  reject: "border-red-200 bg-red-50 text-red-700",
};

export const ACTION_LABEL: Record<FindingActionType, string> = {
  confirm: "Confirmed",
  dismiss: "Dismissed",
};

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date);
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function confidencePercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
