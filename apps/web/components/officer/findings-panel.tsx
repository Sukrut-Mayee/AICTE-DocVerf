"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Crosshair,
  FileSearch,
  MessageSquareWarning,
  X,
} from "lucide-react";

import { ActionBadge, SeverityBadge } from "@/components/officer/badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  submitFindingAction,
  type DocumentStatus,
  type Finding,
  type FindingActionType,
  type Severity,
} from "@/lib/api";
import {
  ACTION_LABEL,
  confidencePercent,
  formatDateTime,
  formatValue,
  humanize,
  SEVERITY_LABEL,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const SEVERITY_FILTERS: Array<Severity | "all"> = ["all", "high", "medium", "low", "info"];

interface FindingsPanelProps {
  findings: Finding[];
  documents: DocumentStatus[];
  selectedFindingId: string | null;
  focusNonce: number;
  onFocusFinding: (finding: Finding) => void;
  onUpdated: () => Promise<void>;
}

interface OtherClaimant {
  app_id: string;
  institute_name?: string;
  doc_id?: string;
}

/** Applications that claim the same land parcel / trust (cross-institution reuse findings). */
function alsoClaimedBy(finding: Finding): OtherClaimant[] {
  const raw = finding.evidence?.also_claimed_by;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (entry): entry is OtherClaimant =>
      !!entry && typeof entry === "object" && typeof (entry as OtherClaimant).app_id === "string",
  );
}

function sourceLabel(documents: DocumentStatus[], docId: string): string {
  const document = documents.find((entry) => entry.doc_id === docId);
  return document?.filename ?? document?.doc_type ?? docId;
}

function EvidenceValue({ value }: { value: unknown }) {
  if (value !== null && typeof value === "object") {
    return (
      <pre className="max-h-40 overflow-auto rounded bg-slate-50 p-2 text-[11px] leading-relaxed text-slate-700 scrollbar-thin">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span className="text-xs text-slate-700">{formatValue(value)}</span>;
}

export function FindingsPanel({
  findings,
  documents,
  selectedFindingId,
  focusNonce,
  onFocusFinding,
  onUpdated,
}: FindingsPanelProps) {
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<FindingActionType | null>(null);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const counts = useMemo(() => {
    return {
      all: findings.length,
      high: findings.filter((finding) => finding.severity === "high").length,
      medium: findings.filter((finding) => finding.severity === "medium").length,
      low: findings.filter((finding) => finding.severity === "low").length,
      info: findings.filter((finding) => finding.severity === "info").length,
    };
  }, [findings]);

  const visibleFindings = useMemo(
    () =>
      filter === "all"
        ? findings
        : findings.filter((finding) => finding.severity === filter),
    [findings, filter],
  );

  useEffect(() => {
    if (!focusNonce || !selectedFindingId) return;
    document
      .getElementById(`finding-${selectedFindingId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [focusNonce, selectedFindingId]);

  function startAction(finding: Finding, action: FindingActionType) {
    setActiveFindingId(finding.finding_id);
    setPendingAction(action);
    setReason(finding.officer_action?.reason ?? "");
    setError(null);
    setSuccess(null);
  }

  function cancelAction() {
    setActiveFindingId(null);
    setPendingAction(null);
    setReason("");
    setError(null);
  }

  async function saveAction(finding: Finding) {
    if (!pendingAction) return;
    if (!reason.trim()) {
      setError("A reason is required before saving the action.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitFindingAction(finding.finding_id, {
        action: pendingAction,
        reason: reason.trim(),
      });
      setSuccess(
        `${ACTION_LABEL[pendingAction]} action saved for ${finding.rule_id ?? finding.finding_id}.`,
      );
      setActiveFindingId(null);
      setPendingAction(null);
      setReason("");
      await onUpdated();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The finding action could not be saved.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader className="border-b p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              Findings
              <Badge variant="secondary">{findings.length}</Badge>
            </CardTitle>
            <CardDescription className="text-xs">
              Pipeline findings with their evidence. Confirm or dismiss each high-severity
              finding with a reason.
            </CardDescription>
          </div>
          <FileSearch className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
        </div>

        <div className="flex flex-wrap gap-1.5 pt-3">
          {SEVERITY_FILTERS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                filter === value
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
              )}
            >
              {value === "all" ? "All" : SEVERITY_LABEL[value]} ({counts[value]})
            </button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="space-y-3 p-3 sm:p-4">
        {success ? (
          <Alert variant="success">
            <CheckCircle2 className="h-4 w-4" />
            <AlertTitle>Action saved</AlertTitle>
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        ) : null}

        {visibleFindings.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-12 text-center">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" aria-hidden="true" />
            <p className="font-medium">
              {findings.length === 0
                ? "No findings for this application"
                : "No findings match this filter"}
            </p>
            <p className="max-w-sm text-sm text-muted-foreground">
              {findings.length === 0
                ? "Review the documents and record a decision when ready."
                : "Choose another severity filter to see the remaining findings."}
            </p>
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-1">
            {visibleFindings.map((finding) => {
            const selected = finding.finding_id === selectedFindingId;
            const editing = activeFindingId === finding.finding_id;
            const hasLocation = finding.claims.some(
              (claim) => claim.bbox && claim.page,
            );
            return (
              <article
                key={finding.finding_id}
                id={`finding-${finding.finding_id}`}
                className={cn(
                  "rounded-lg border border-l-4 bg-white p-3 transition-shadow sm:p-3.5",
                  finding.severity === "high" && "border-l-red-500",
                  finding.severity === "medium" && "border-l-amber-500",
                  finding.severity === "low" && "border-l-sky-500",
                  finding.severity === "info" && "border-l-slate-400",
                  selected && "ring-2 ring-slate-900/15",
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={finding.severity} />
                    <Badge variant="outline" className="bg-slate-50 text-slate-600">
                      {humanize(finding.type)}
                    </Badge>
                    {finding.rule_id ? (
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold text-slate-700">
                        {finding.rule_id}
                      </code>
                    ) : null}
                    {finding.officer_action ? (
                      <ActionBadge action={finding.officer_action.action} />
                    ) : (
                      <Badge
                        variant="outline"
                        className="border-amber-200 bg-amber-50 text-amber-800"
                      >
                        Needs action
                      </Badge>
                    )}
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onFocusFinding(finding)}
                    title="Show this evidence on the PDF"
                  >
                    <Crosshair className="h-3.5 w-3.5" />
                    Show on document
                  </Button>
                </div>

                <p className="mt-2 text-sm font-medium leading-relaxed">{finding.message}</p>

                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {finding.entity ? (
                    <span>
                      Entity: <span className="font-medium text-slate-700">{finding.entity}</span>
                    </span>
                  ) : null}
                  {finding.attribute ? (
                    <span>
                      Attribute:{" "}
                      <span className="font-medium text-slate-700">{finding.attribute}</span>
                    </span>
                  ) : null}
                  {finding.layer ? <span>Layer {finding.layer}</span> : null}
                  <span className="font-mono">{finding.finding_id}</span>
                </div>

                {finding.claims.length > 0 ? (
                  <div className="mt-3 space-y-1.5">
                    {finding.claims.map((claim, index) => (
                      <div
                        key={`${finding.finding_id}-claim-${index}`}
                        className="rounded-md border bg-slate-50/70 px-2.5 py-2"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
                          <span className="min-w-0 break-words text-xs font-medium text-slate-800">
                            {sourceLabel(documents, claim.doc_id)}
                          </span>
                          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                            {humanize(claim.authority)}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                          <span className="font-medium text-slate-700">
                            {formatValue(claim.value)}
                          </span>
                          <span>Confidence {confidencePercent(claim.confidence)}</span>
                          <span>
                            {claim.page && claim.bbox
                              ? `Page ${claim.page}`
                              : "No location"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                {!hasLocation ? (
                  <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <MessageSquareWarning className="h-3.5 w-3.5" aria-hidden="true" />
                    No bounding box was supplied for this finding; review the values and
                    document text instead.
                  </p>
                ) : null}

                {alsoClaimedBy(finding).length > 0 ? (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
                    <p className="font-medium">Also claimed by</p>
                    <ul className="mt-1 space-y-0.5">
                      {alsoClaimedBy(finding).map((other) => (
                        <li key={`${other.app_id}-${other.doc_id}`}>
                          <Link
                            href={`/officer/applications/${encodeURIComponent(other.app_id)}`}
                            className="font-medium text-sky-800 underline"
                          >
                            {other.app_id}
                          </Link>
                          {other.institute_name ? ` · ${other.institute_name}` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {Object.keys(finding.evidence ?? {}).length > 0 ? (
                  <details className="mt-3 rounded-md border bg-slate-50/60">
                    <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-700">
                      Structured evidence ({Object.keys(finding.evidence).length} fields)
                    </summary>
                    <div className="space-y-2 border-t px-3 py-2">
                      {Object.entries(finding.evidence).map(([key, value]) => (
                        <div key={key} className="grid gap-1 sm:grid-cols-[160px_1fr]">
                          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                            {humanize(key)}
                          </span>
                          <EvidenceValue value={value} />
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}

                {finding.officer_action && !editing ? (
                  <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
                    <div className="flex flex-wrap items-center gap-2 font-medium">
                      <Check className="h-3.5 w-3.5" />
                      {ACTION_LABEL[finding.officer_action.action]} by{" "}
                      {finding.officer_action.actor}
                      <span className="font-normal text-emerald-700">
                        {formatDateTime(finding.officer_action.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 text-emerald-800">{finding.officer_action.reason}</p>
                  </div>
                ) : null}

                {editing ? (
                  <div className="mt-3 rounded-md border border-slate-300 bg-slate-50 p-3">
                    <p className="text-sm font-medium">
                      {pendingAction === "confirm" ? "Confirm" : "Dismiss"} this finding
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Your reason is saved with the action and shown after a reload.
                    </p>
                    <Textarea
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      placeholder="Explain what you checked and why you are confirming or dismissing this finding."
                      className="mt-2 min-h-[88px] bg-white"
                      disabled={submitting}
                      autoFocus
                    />
                    {error ? (
                      <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-red-700">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {error}
                      </p>
                    ) : null}
                    <div className="mt-2 flex items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void saveAction(finding)}
                        disabled={submitting || !reason.trim()}
                      >
                        {submitting ? "Saving…" : `Save ${pendingAction ?? "action"}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={cancelAction}
                        disabled={submitting}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => startAction(finding, "confirm")}
                    >
                      <Check className="h-3.5 w-3.5" />
                      {finding.officer_action ? "Change to confirm" : "Confirm finding"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => startAction(finding, "dismiss")}
                    >
                      <X className="h-3.5 w-3.5" />
                      {finding.officer_action ? "Change to dismiss" : "Dismiss finding"}
                    </Button>
                  </div>
                )}
              </article>
            );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
