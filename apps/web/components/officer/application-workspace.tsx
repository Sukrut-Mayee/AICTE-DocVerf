"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";

import { DecisionPanel } from "@/components/officer/decision-panel";
import { DocumentList } from "@/components/officer/document-list";
import { FindingsPanel } from "@/components/officer/findings-panel";
import { PdfViewer } from "@/components/officer/pdf-viewer";
import { SummaryBar } from "@/components/officer/summary-bar";
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
  ApiError,
  getApplicationBundle,
  type ApplicationBundle,
  type Finding,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function WorkspaceSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-56 w-full rounded-xl" />
      <div className="grid gap-4 lg:grid-cols-[minmax(200px,240px)_minmax(0,1fr)] 2xl:grid-cols-[minmax(200px,240px)_minmax(0,1fr)_minmax(360px,420px)]">
        <Skeleton className="h-72 w-full rounded-xl lg:h-[520px]" />
        <Skeleton className="h-[520px] w-full rounded-xl" />
        <Skeleton className="h-[620px] w-full rounded-xl lg:col-span-2 2xl:col-span-1" />
      </div>
    </div>
  );
}

export function ApplicationWorkspace({ appId }: { appId: string }) {
  const [bundle, setBundle] = useState<ApplicationBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);

  const load = useCallback(
    async (initial: boolean) => {
      if (initial) setLoading(true);
      else setRefreshing(true);
      setError(null);
      try {
        const next = await getApplicationBundle(appId);
        setBundle(next);
        setSelectedDocId((current) => {
          if (current && next.documents.some((document) => document.doc_id === current)) {
            return current;
          }
          const preferred =
            next.documents.find(
              (document) => document.previewable && document.overall !== "no_issues",
            ) ??
            next.documents.find((document) => document.previewable) ??
            next.documents[0];
          return preferred?.doc_id ?? null;
        });
        setSelectedFindingId((current) => {
          if (current && next.findings.some((finding) => finding.finding_id === current)) {
            return current;
          }
          return next.findings[0]?.finding_id ?? null;
        });
      } catch (caught) {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "The application could not be loaded.",
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [appId],
  );

  useEffect(() => {
    void load(true);
  }, [load]);

  const selectedDocument =
    bundle?.documents.find((document) => document.doc_id === selectedDocId) ?? null;

  function focusFinding(finding: Finding) {
    setSelectedFindingId(finding.finding_id);
    setFocusNonce((current) => current + 1);
    const claimDoc = finding.claims.find(
      (claim) => claim.doc_id && claim.page && claim.bbox,
    )?.doc_id;
    const claimDocExists =
      claimDoc && bundle?.documents.some((document) => document.doc_id === claimDoc);
    const candidate =
      (claimDocExists ? claimDoc : undefined) ??
      finding.doc_ids.find((docId) =>
        bundle?.documents.some((document) => document.doc_id === docId),
      );
    if (candidate) setSelectedDocId(candidate);
  }

  function focusFindingById(findingId: string) {
    setSelectedFindingId(findingId);
    setFocusNonce((current) => current + 1);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/officer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Review queue
        </Link>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void load(false)}
          disabled={refreshing}
        >
          <RefreshCw
            className={cn("h-3.5 w-3.5", refreshing && "animate-spin")}
            aria-hidden="true"
          />
          {refreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {loading && !bundle ? (
        <WorkspaceSkeleton />
      ) : error && !bundle ? (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not open {appId}</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{error}</p>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => void load(true)}>
                Try again
              </Button>
              <Button asChild size="sm" variant="ghost">
                <Link href="/officer">Back to queue</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : bundle ? (
        <>
          {error ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Refresh failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <SummaryBar summary={bundle.summary} />

          <div className="grid gap-4 lg:grid-cols-[minmax(200px,240px)_minmax(0,1fr)] 2xl:grid-cols-[minmax(200px,240px)_minmax(0,1fr)_minmax(360px,420px)] lg:items-start">
            <div className="min-w-0 2xl:sticky 2xl:top-20 2xl:max-h-[calc(100vh-6rem)] 2xl:overflow-y-auto 2xl:overscroll-contain 2xl:pr-1 scrollbar-thin">
              <DocumentList
                documents={bundle.documents}
                selectedDocId={selectedDocId}
                onSelect={setSelectedDocId}
              />
            </div>

            <Card className="min-w-0 overflow-hidden">
              <CardHeader className="border-b p-4 pb-3">
                <CardTitle className="flex min-w-0 flex-wrap items-center gap-2 text-base">
                  Document preview
                  {selectedDocument ? (
                    <span className="min-w-0 truncate font-mono text-xs font-normal text-muted-foreground">
                      {selectedDocument.filename ?? selectedDocument.doc_id}
                    </span>
                  ) : null}
                </CardTitle>
                <CardDescription className="text-xs">
                  {selectedDocument
                    ? selectedDocument.note
                    : "Select a document to view its pages and evidence boxes."}
                </CardDescription>
              </CardHeader>
              <CardContent className="p-3 sm:p-4">
                <PdfViewer
                  document={selectedDocument}
                  findings={bundle.findings}
                  selectedFindingId={selectedFindingId}
                  onSelectFinding={focusFindingById}
                />
              </CardContent>
            </Card>

            <div className="min-w-0 space-y-4 lg:col-span-2 2xl:col-span-1 2xl:sticky 2xl:top-20 2xl:max-h-[calc(100vh-6rem)] 2xl:overflow-y-auto 2xl:overscroll-contain 2xl:pr-1 scrollbar-thin">
              <FindingsPanel
                findings={bundle.findings}
                documents={bundle.documents}
                selectedFindingId={selectedFindingId}
                focusNonce={focusNonce}
                onFocusFinding={focusFinding}
                onUpdated={() => load(false)}
              />
              <DecisionPanel summary={bundle.summary} onUpdated={() => load(false)} />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
