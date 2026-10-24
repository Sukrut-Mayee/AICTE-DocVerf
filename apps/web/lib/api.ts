/**
 * Single client for the FastAPI officer API.
 *
 * Every network call used by the dashboard lives here so the UI never talks to the
 * backend directly. Override the API origin with NEXT_PUBLIC_API_BASE_URL.
 */

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export type Severity = "high" | "medium" | "low" | "info";
export type FindingActionType = "confirm" | "dismiss";
export type AuthorityTier = "issuer_verified" | "third_party" | "self_declared";
export type OverallStatus = "no_issues" | "flagged" | "manual_review_required";
export type VerificationStatus =
  | "verified"
  | "mismatch_detected"
  | "expired"
  | "verification_pending"
  | "source_unavailable"
  | "manual_review_required";
export type DecisionType =
  | "approve"
  | "approve_with_deficiencies"
  | "request_rectification"
  | "site_inspection"
  | "reject";

export interface Claim {
  doc_id: string;
  entity: string;
  attribute: string;
  value: unknown;
  authority: AuthorityTier;
  confidence: number;
  page: number | null;
  bbox: number[] | null;
}

export interface Finding {
  finding_id: string;
  app_id: string;
  type: string;
  severity: Severity;
  layer: string | null;
  rule_id: string | null;
  entity: string | null;
  attribute: string | null;
  claims: Claim[];
  doc_ids: string[];
  message: string;
  evidence: Record<string, unknown>;
  officer_action: ActionRecord | null;
}

export interface ActionRecord {
  finding_id: string;
  app_id: string;
  action: FindingActionType;
  reason: string;
  actor: string;
  created_at: string;
}

export interface DecisionRecord {
  app_id: string;
  decision: DecisionType;
  reason: string;
  deficiencies: string[];
  actor: string;
  created_at: string;
}

export interface DocumentStatus {
  doc_id: string;
  overall: OverallStatus;
  verification: VerificationStatus | null;
  note: string;
  finding_ids: string[];
  doc_type: string | null;
  filename: string | null;
  file_url: string | null;
  previewable: boolean;
  high_findings: number;
  max_severity: Severity | null;
}

export interface FindingCounts {
  total: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface DocumentCounts {
  total: number;
  flagged: number;
  manual_review: number;
  no_issues: number;
}

export interface AuditRef {
  seq: number;
  hash: string | null;
  tx: string | null;
}

export interface ApplicationSummary {
  app_id: string;
  institute_name: string | null;
  application_no: string | null;
  status: "review_pending" | "decided";
  priority: number;
  finding_counts: FindingCounts;
  document_counts: DocumentCounts;
  checks_count: number;
  high_pending: number;
  decision_allowed: boolean;
  decision: DecisionRecord | null;
  audit: AuditRef | null;
  meta: Record<string, unknown>;
}

export type QueueItem = ApplicationSummary;

export interface ApplicationBundle {
  summary: ApplicationSummary;
  documents: DocumentStatus[];
  findings: Finding[];
}

export interface FindingActionInput {
  action: FindingActionType;
  reason: string;
}

export interface DecisionInput {
  decision: DecisionType;
  reason: string;
  deficiencies: string[];
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(
      `Cannot reach the DocVerf API at ${API_BASE_URL}. Start the backend and try again.`,
      0,
      null,
    );
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = body?.detail ?? body;
    } catch {
      detail = null;
    }
    throw new ApiError(
      detailMessage(detail, `The API rejected the request (HTTP ${response.status}).`),
      response.status,
      detail,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function listApplications(status?: string): Promise<QueueItem[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<QueueItem[]>(`/v1/applications${query}`);
}

export function getApplication(appId: string): Promise<ApplicationSummary> {
  return request<ApplicationSummary>(`/v1/applications/${encodeURIComponent(appId)}`);
}

export function getDocuments(appId: string): Promise<DocumentStatus[]> {
  return request<DocumentStatus[]>(
    `/v1/applications/${encodeURIComponent(appId)}/documents`,
  );
}

export function getFindings(appId: string): Promise<Finding[]> {
  return request<Finding[]>(`/v1/applications/${encodeURIComponent(appId)}/findings`);
}

export async function getApplicationBundle(appId: string): Promise<ApplicationBundle> {
  const [summary, documents, findings] = await Promise.all([
    getApplication(appId),
    getDocuments(appId),
    getFindings(appId),
  ]);
  return { summary, documents, findings };
}

export function submitFindingAction(
  findingId: string,
  input: FindingActionInput,
): Promise<ActionRecord> {
  return request<ActionRecord>(
    `/v1/findings/${encodeURIComponent(findingId)}/action`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function submitDecision(
  appId: string,
  input: DecisionInput,
): Promise<DecisionRecord> {
  return request<DecisionRecord>(
    `/v1/applications/${encodeURIComponent(appId)}/decision`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function documentFileUrl(fileUrl: string | null): string | null {
  if (!fileUrl) return null;
  if (/^https?:\/\//i.test(fileUrl)) return fileUrl;
  return `${API_BASE_URL}${fileUrl.startsWith("/") ? "" : "/"}${fileUrl}`;
}
