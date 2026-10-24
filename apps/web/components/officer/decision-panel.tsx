"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileWarning,
  LockKeyhole,
  MapPin,
  RotateCcw,
  XCircle,
} from "lucide-react";

import { DecisionBadge } from "@/components/officer/badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  submitDecision,
  type ApplicationSummary,
  type DecisionType,
} from "@/lib/api";
import {
  DECISION_DESCRIPTION,
  DECISION_LABEL,
  formatDateTime,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const DECISION_OPTIONS: Array<{
  value: DecisionType;
  icon: typeof CheckCircle2;
}> = [
  { value: "approve", icon: CheckCircle2 },
  { value: "approve_with_deficiencies", icon: FileWarning },
  { value: "request_rectification", icon: RotateCcw },
  { value: "site_inspection", icon: MapPin },
  { value: "reject", icon: XCircle },
];

const DEFICIENCY_DECISIONS = new Set<DecisionType>([
  "approve_with_deficiencies",
  "request_rectification",
  "site_inspection",
]);

interface DecisionPanelProps {
  summary: ApplicationSummary;
  onUpdated: () => Promise<void>;
}

export function DecisionPanel({ summary, onUpdated }: DecisionPanelProps) {
  const [decision, setDecision] = useState<DecisionType>(
    summary.decision?.decision ?? "approve",
  );
  const [reason, setReason] = useState("");
  const [deficiencies, setDeficiencies] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const locked = !summary.decision_allowed;
  const needsDeficiencies = DEFICIENCY_DECISIONS.has(decision);
  const reasonRequired = decision === "reject";

  async function record() {
    if (locked) return;
    if (reasonRequired && !reason.trim()) {
      setError("A reason is required when rejecting an application.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const parsedDeficiencies = needsDeficiencies
        ? deficiencies
            .split(/[\n,]/)
            .map((entry) => entry.trim())
            .filter(Boolean)
        : [];
      const record = await submitDecision(summary.app_id, {
        decision,
        reason: reason.trim(),
        deficiencies: parsedDeficiencies,
      });
      setSuccess(
        `${DECISION_LABEL[record.decision]} recorded for ${record.app_id}.`,
      );
      setReason("");
      setDeficiencies("");
      await onUpdated();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The decision could not be recorded.",
      );
      if (caught instanceof ApiError && caught.status === 409) {
        await onUpdated();
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader className="border-b p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Decision</CardTitle>
            <CardDescription className="text-xs">
              The officer records the final decision. The system never decides on its own.
            </CardDescription>
          </div>
          {locked ? (
            <LockKeyhole className="h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden="true" />
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 p-4">
        {summary.decision ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Recorded decision
              </span>
              <DecisionBadge decision={summary.decision.decision} />
              <span className="text-xs text-muted-foreground">
                {formatDateTime(summary.decision.created_at)}
              </span>
            </div>
            {summary.decision.reason ? (
              <p className="mt-1.5 text-sm text-slate-700">{summary.decision.reason}</p>
            ) : null}
            {summary.decision.deficiencies.length > 0 ? (
              <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-slate-600">
                {summary.decision.deficiencies.map((deficiency) => (
                  <li key={deficiency}>{deficiency}</li>
                ))}
              </ul>
            ) : null}
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              Recorded by {summary.decision.actor}. The form below records a revised
              decision.
            </p>
          </div>
        ) : null}

        {locked ? (
          <Alert variant="warning">
            <LockKeyhole className="h-4 w-4" />
            <AlertTitle>Decision locked</AlertTitle>
            <AlertDescription>
              {summary.high_pending} high-severity finding
              {summary.high_pending === 1 ? "" : "s"} still need a confirm or dismiss action.
              Use the findings panel to review them first.
            </AlertDescription>
          </Alert>
        ) : null}

        {success ? (
          <Alert variant="success">
            <CheckCircle2 className="h-4 w-4" />
            <AlertTitle>Decision recorded</AlertTitle>
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        ) : null}

        {error ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Could not record the decision</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <fieldset className="space-y-2" disabled={locked || submitting}>
          <legend className="text-sm font-medium">Choose an outcome</legend>
          <div className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-1">
            {DECISION_OPTIONS.map((option) => {
              const Icon = option.icon;
              const active = decision === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    setDecision(option.value);
                    setError(null);
                  }}
                  aria-pressed={active}
                  className={cn(
                    "flex items-start gap-2.5 rounded-lg border p-2.5 text-left transition-colors",
                    active
                      ? "border-slate-900 bg-slate-50 ring-1 ring-slate-900/10"
                      : "bg-white hover:bg-slate-50",
                    (locked || submitting) && "cursor-not-allowed opacity-60",
                  )}
                >
                  <Icon
                    className={cn(
                      "mt-0.5 h-4 w-4 shrink-0",
                      option.value === "reject" ? "text-red-600" : "text-slate-600",
                    )}
                    aria-hidden="true"
                  />
                  <span>
                    <span className="block text-sm font-medium">
                      {DECISION_LABEL[option.value]}
                      {option.value === "reject" ? (
                        <span className="ml-1 text-xs font-normal text-red-700">
                          (reason required)
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {DECISION_DESCRIPTION[option.value]}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="space-y-2">
          <Label htmlFor="decision-reason">
            Decision reason{reasonRequired ? " (required)" : " (optional)"}
          </Label>
          <Textarea
            id="decision-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={
              reasonRequired
                ? "Explain why this application is being rejected."
                : "Summarise the review and the basis for this decision."
            }
            disabled={locked || submitting}
            className="min-h-[88px]"
          />
        </div>

        {needsDeficiencies ? (
          <div className="space-y-2">
            <Label htmlFor="decision-deficiencies">
              Deficiencies / follow-up items (one per line)
            </Label>
            <Textarea
              id="decision-deficiencies"
              value={deficiencies}
              onChange={(event) => setDeficiencies(event.target.value)}
              placeholder={"Provide a NOC valid through the academic year.\nSubmit a corrected land deed."}
              disabled={locked || submitting}
              className="min-h-[88px]"
            />
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
          <p className="text-xs text-muted-foreground">
            {locked
              ? "The backend also rejects a locked decision with HTTP 409."
              : "Every high-severity finding has an action."}
          </p>
          <Button
            type="button"
            onClick={() => void record()}
            disabled={locked || submitting}
          >
            {submitting ? "Recording…" : "Record decision"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
