"use client";

import { useState } from "react";
import { ChevronRight, FileText, Image as ImageIcon, Layers } from "lucide-react";

import { OverallBadge, SeverityBadge, VerificationBadge } from "@/components/officer/badges";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { DocumentStatus } from "@/lib/api";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

interface DocumentListProps {
  documents: DocumentStatus[];
  selectedDocId: string | null;
  onSelect: (docId: string) => void;
}

function DocumentButton({
  document,
  selected,
  onSelect,
}: {
  document: DocumentStatus;
  selected: boolean;
  onSelect: (docId: string) => void;
}) {
  const isImage = document.filename?.match(/\.(png|jpe?g)$/i);
  const Icon = isImage ? ImageIcon : FileText;
  return (
    <button
      type="button"
      onClick={() => onSelect(document.doc_id)}
      className={cn(
        "w-full rounded-lg border bg-white p-2.5 text-left transition-colors hover:border-slate-300 hover:bg-slate-50/60",
        selected && "border-slate-900 ring-1 ring-slate-900/10",
      )}
      aria-pressed={selected}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-md bg-slate-100 p-1.5 text-slate-600">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">
            {humanize(document.doc_type ?? document.doc_id)}
          </span>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <OverallBadge overall={document.overall} />
            {document.max_severity ? (
              <SeverityBadge severity={document.max_severity} />
            ) : null}
          </div>
          <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
            {document.note}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted-foreground">
            <span className="block w-full truncate font-mono">
              {document.filename ?? document.doc_id}
            </span>
            {document.finding_ids.length > 0 ? (
              <span className="flex items-center gap-1">
                <Layers className="h-3 w-3" aria-hidden="true" />
                {document.finding_ids.length} linked finding
                {document.finding_ids.length === 1 ? "" : "s"}
                {document.high_findings > 0 ? ` · ${document.high_findings} high` : ""}
              </span>
            ) : (
              <span>No linked findings</span>
            )}
            {document.verification ? (
              <VerificationBadge status={document.verification} />
            ) : null}
            {!document.filename ? (
              <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
                File not found
              </Badge>
            ) : null}
          </div>
        </div>
      </div>
    </button>
  );
}

export function DocumentList({ documents, selectedDocId, onSelect }: DocumentListProps) {
  const [cleanOpen, setCleanOpen] = useState(false);
  const flagged = documents.filter((document) => document.overall !== "no_issues");
  const clean = documents.filter((document) => document.overall === "no_issues");

  return (
    <Card>
      <CardHeader className="border-b p-4">
        <CardTitle className="flex items-center gap-2">
          Documents
          <Badge variant="secondary">{documents.length}</Badge>
        </CardTitle>
        <CardDescription className="text-xs">
          Flagged documents first. Select one to preview it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 p-3 xl:p-2">
        {documents.length === 0 ? (
          <p className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            The pipeline did not report any documents for this application.
          </p>
        ) : null}

        {flagged.map((document) => (
          <DocumentButton
            key={document.doc_id}
            document={document}
            selected={document.doc_id === selectedDocId}
            onSelect={onSelect}
          />
        ))}

        {clean.length > 0 ? (
          <div className="rounded-lg border bg-slate-50/60">
            <button
              type="button"
              onClick={() => setCleanOpen((open) => !open)}
              className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
              aria-expanded={cleanOpen}
            >
              <span className="text-sm font-medium text-slate-700">
                {clean.length} document{clean.length === 1 ? "" : "s"} with no issues
              </span>
              <ChevronRight
                className={cn("h-4 w-4 text-slate-500 transition-transform", cleanOpen && "rotate-90")}
                aria-hidden="true"
              />
            </button>
            {cleanOpen ? (
              <div className="space-y-2 border-t p-2">
                {clean.map((document) => (
                  <DocumentButton
                    key={document.doc_id}
                    document={document}
                    selected={document.doc_id === selectedDocId}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
