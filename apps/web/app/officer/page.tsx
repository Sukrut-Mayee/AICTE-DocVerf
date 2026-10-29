"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Inbox,
  ListChecks,
  LockKeyhole,
  RefreshCw,
} from "lucide-react";

import { DecisionBadge, StatusBadge } from "@/components/officer/badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, listApplications, type QueueItem } from "@/lib/api";
import { FALLBACK_SOURCE, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

function priorityClass(priority: number): string {
  if (priority >= 300) return "border-red-200 bg-red-50 text-red-700";
  if (priority >= 100) return "border-amber-200 bg-amber-50 text-amber-800";
  if (priority > 0) return "border-sky-200 bg-sky-50 text-sky-700";
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number | string;
  hint: string;
  icon: typeof ListChecks;
  tone: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between p-5">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
        </div>
        <span className={cn("rounded-lg p-2", tone)}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      </CardContent>
    </Card>
  );
}

function QueueSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index}>
            <CardContent className="space-y-3 p-5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="space-y-3 p-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-14 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export default function OfficerQueuePage() {
  const [queue, setQueue] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setQueue(await listApplications());
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The review queue could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const stats = useMemo(() => {
    const items = queue ?? [];
    return {
      total: items.length,
      awaiting: items.filter((item) => item.status === "review_pending").length,
      decided: items.filter((item) => item.status === "decided").length,
      highPending: items.reduce((total, item) => total + item.high_pending, 0),
    };
  }, [queue]);

  const mockItems = (queue ?? []).filter((item) => item.meta?.source === "mock_fixture");
  const fallbackItems = (queue ?? []).filter((item) => item.meta?.source === FALLBACK_SOURCE);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Officer review
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Applications awaiting review
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Sorted by risk: high-severity findings first. Open an
            application to inspect evidence, act on findings, and record a decision.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
          Refresh queue
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load the review queue</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-3">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={() => void load()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {loading && queue === null ? (
        <QueueSkeleton />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Applications"
              value={stats.total}
              hint="With pipeline output available"
              icon={Inbox}
              tone="bg-slate-100 text-slate-600"
            />
            <StatCard
              label="Awaiting review"
              value={stats.awaiting}
              hint="No decision recorded yet"
              icon={Clock3}
              tone="bg-amber-100 text-amber-700"
            />
            <StatCard
              label="High flags pending"
              value={stats.highPending}
              hint="Findings still needing an action"
              icon={AlertTriangle}
              tone="bg-red-100 text-red-700"
            />
            <StatCard
              label="Decisions recorded"
              value={stats.decided}
              hint="Recorded by an officer"
              icon={CheckCircle2}
              tone="bg-emerald-100 text-emerald-700"
            />
          </div>

          {mockItems.length > 0 ? (
            <Alert variant="info">
              <ListChecks className="h-4 w-4" />
              <AlertTitle>Demo fixture data in use</AlertTitle>
              <AlertDescription>
                {mockItems.map((item) => item.app_id).join(", ")} is seeded from{" "}
                <code className="rounded bg-sky-100 px-1 py-0.5 text-xs">
                  tests/fixtures/apps/app_conflict
                </code>
                . Replacing it with real pipeline output needs no UI change.
              </AlertDescription>
            </Alert>
          ) : null}

          {fallbackItems.length > 0 ? (
            <Alert variant="info">
              <ListChecks className="h-4 w-4" />
              <AlertTitle>Not live pipeline output</AlertTitle>
              <AlertDescription>
                {fallbackItems.length === (queue ?? []).length
                  ? "All applications"
                  : fallbackItems.map((item) => item.app_id).join(", ")}{" "}
                are built from the synthetic ground truth (perfect extraction, no provenance,
                forensic or issuer checks). Real pipeline output replaces them with no UI change.
              </AlertDescription>
            </Alert>
          ) : null}

          <Card>
            <CardHeader className="flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle>Review queue</CardTitle>
                <CardDescription>
                  Flag counts come from the pipeline findings; pending counts reflect
                  officer actions you have recorded.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {queue && queue.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
                  <Inbox className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
                  <p className="font-medium">No applications found</p>
                  <p className="max-w-md text-sm text-muted-foreground">
                    The API did not find any files in{" "}
                    <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">
                      data/out/pipeline/
                    </code>
                    . Run the pipeline or seed the demo fixture, then refresh.
                  </p>
                </div>
              ) : (
                <Table className="min-w-[940px] table-fixed">
                  <colgroup>
                    <col className="w-[30%]" />
                    <col className="w-[8%]" />
                    <col className="w-[25%]" />
                    <col className="w-[15%]" />
                    <col className="w-[12%]" />
                    <col className="w-[10%]" />
                  </colgroup>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Application</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Findings</TableHead>
                      <TableHead>Documents</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Review</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(queue ?? []).map((item) => (
                      <TableRow key={item.app_id}>
                        <TableCell>
                          <Link
                            href={`/officer/applications/${item.app_id}`}
                            className="group block"
                          >
                            <span className="block truncate font-mono text-xs font-semibold text-primary group-hover:underline">
                              {item.app_id}
                            </span>
                            <span className="mt-0.5 block truncate font-medium">
                              {item.institute_name ?? "Institute not extracted"}
                            </span>
                            <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                              {item.application_no
                                ? `Application ${item.application_no}`
                                : "Application number unavailable"}
                            </span>
                          </Link>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          <span
                            className={cn(
                              "inline-flex rounded-md border px-2 py-1 font-mono text-xs font-semibold",
                              priorityClass(item.priority),
                            )}
                          >
                            {item.priority}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="whitespace-nowrap text-sm font-medium">
                              {item.finding_counts.total} total
                            </span>
                            {item.finding_counts.high > 0 ? (
                              <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[11px] font-semibold text-red-700">
                                {item.finding_counts.high} high
                              </span>
                            ) : null}
                            {item.finding_counts.medium > 0 ? (
                              <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[11px] font-semibold text-amber-800">
                                {item.finding_counts.medium} med
                              </span>
                            ) : null}
                            {item.finding_counts.low > 0 ? (
                              <span className="rounded border border-sky-200 bg-sky-50 px-1.5 py-0.5 text-[11px] font-semibold text-sky-700">
                                {item.finding_counts.low} low
                              </span>
                            ) : null}
                          </div>
                          {item.high_pending > 0 ? (
                            <span className="mt-1 flex items-center gap-1 whitespace-nowrap text-xs text-red-700">
                              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                              {item.high_pending} high pending
                            </span>
                          ) : (
                            <span className="mt-1 block text-xs text-muted-foreground">
                              All high findings handled
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          <span className="text-sm font-medium">
                            {item.document_counts.flagged} flagged /{" "}
                            {item.document_counts.total}
                          </span>
                          <span className="mt-0.5 block text-xs text-muted-foreground">
                            {item.document_counts.manual_review} manual ·{" "}
                            {item.document_counts.no_issues} clean
                          </span>
                        </TableCell>
                        <TableCell>
                          {item.decision ? (
                            <div className="space-y-1">
                              <DecisionBadge decision={item.decision.decision} />
                              <p className="text-xs text-muted-foreground">
                                {formatDateTime(item.decision.created_at)}
                              </p>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <StatusBadge status={item.status} />
                              {!item.decision_allowed ? (
                                <p className="flex items-center gap-1 text-xs text-amber-700">
                                  <LockKeyhole className="h-3 w-3" aria-hidden="true" />
                                  Decision locked
                                </p>
                              ) : (
                                <p className="text-xs text-emerald-700">Ready for decision</p>
                              )}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-right">
                          <Button asChild size="sm" variant="outline">
                            <Link href={`/officer/applications/${item.app_id}`}>
                              Open
                              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                            </Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {queue && queue.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              Priorities are shown exactly as emitted by the pipeline. High-severity
              findings require an officer action before a decision can be recorded.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
