import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileText,
  Fingerprint,
  LockKeyhole,
} from "lucide-react";

import { DecisionBadge, StatusBadge } from "@/components/officer/badges";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { ApplicationSummary } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string | number;
  hint: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border bg-white px-2.5 py-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-0.5 text-lg font-semibold tracking-tight", tone)}>{value}</p>
      <p className="text-[10px] leading-snug text-muted-foreground">{hint}</p>
    </div>
  );
}

export function SummaryBar({ summary }: { summary: ApplicationSummary }) {
  const isMock = summary.meta?.source === "mock_fixture";
  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-semibold text-primary">
                {summary.app_id}
              </span>
              <StatusBadge status={summary.status} />
              {summary.decision ? (
                <DecisionBadge decision={summary.decision.decision} />
              ) : null}
              {isMock ? (
                <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">
                  Fixture data
                </Badge>
              ) : null}
              {summary.decision_allowed ? (
                <Badge
                  variant="outline"
                  className="border-emerald-200 bg-emerald-50 text-emerald-700"
                >
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  Decision ready
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="border-amber-200 bg-amber-50 text-amber-800"
                >
                  <LockKeyhole className="mr-1 h-3 w-3" />
                  Locked
                </Badge>
              )}
            </div>
            <h1 className="mt-1.5 text-2xl font-semibold tracking-tight">
              {summary.institute_name ?? "Institute name unavailable"}
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {summary.application_no
                ? `Application ${summary.application_no}`
                : "Application number not extracted"}
            </p>
          </div>

          <div className="rounded-lg border bg-slate-50 px-3 py-1.5 text-right">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Priority
            </p>
            <p className="font-mono text-xl font-semibold">{summary.priority}</p>
            <p className="text-[10px] text-muted-foreground">100 × high + 10 × medium + low</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Metric
            label="Findings"
            value={summary.finding_counts.total}
            hint={`${summary.finding_counts.high} high · ${summary.finding_counts.medium} medium · ${summary.finding_counts.low} low`}
          />
          <Metric
            label="Documents"
            value={summary.document_counts.total}
            hint={`${summary.document_counts.flagged} flagged · ${summary.document_counts.manual_review} manual`}
          />
          <Metric
            label="High pending"
            value={summary.high_pending}
            hint={
              summary.high_pending === 0
                ? "All high findings have an action"
                : "Needs officer action before a decision"
            }
            tone={summary.high_pending > 0 ? "text-red-700" : "text-emerald-700"}
          />
          <Metric
            label="Checks"
            value={summary.checks_count}
            hint="Provenance / forensic checks in output"
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg border bg-slate-50/70 px-2.5 py-1.5 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <ClipboardList className="h-3.5 w-3.5" aria-hidden="true" />
            {summary.finding_counts.total} findings
          </span>
          <span className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            {summary.document_counts.flagged} flagged documents
          </span>
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
            {summary.high_pending} high pending
          </span>
          <span className="flex items-center gap-1.5">
            <Fingerprint className="h-3.5 w-3.5" aria-hidden="true" />
            Pipeline audit seq {summary.audit?.seq ?? "—"}
            {summary.audit?.tx
              ? ` · tx ${summary.audit.tx.slice(0, 10)}…`
              : " · not anchored"}
          </span>
          {summary.decision ? (
            <span>
              Decision recorded {formatDateTime(summary.decision.created_at)}
            </span>
          ) : null}
        </div>

        {isMock ? (
          <p className="text-[11px] leading-relaxed text-sky-800">
            This application is a demo fixture built from{" "}
            <code className="rounded bg-sky-50 px-1 py-0.5">
              tests/fixtures/apps/app_conflict
            </code>
            . Officer actions and decisions are real SQLite records; the findings and audit
            reference were not produced by a live pipeline run.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
