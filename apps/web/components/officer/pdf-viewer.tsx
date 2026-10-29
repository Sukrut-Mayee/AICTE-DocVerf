"use client";

import dynamic from "next/dynamic";
import { FileWarning, FileText } from "lucide-react";

import { ImageViewer } from "@/components/officer/image-viewer";
import { documentFileUrl, type DocumentStatus, type Finding } from "@/lib/api";

const PdfViewerClient = dynamic(() => import("./pdf-viewer-client"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] items-center justify-center rounded-lg border border-dashed bg-slate-50 text-sm text-muted-foreground">
      Loading PDF renderer…
    </div>
  ),
});

interface PdfViewerProps {
  document: DocumentStatus | null;
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

export function PdfViewer({
  document,
  findings,
  selectedFindingId,
  onSelectFinding,
}: PdfViewerProps) {
  const url = documentFileUrl(document?.file_url ?? null);

  if (!document) {
    return (
      <div className="flex h-[360px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-slate-50 px-6 text-center">
        <FileText className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium">Select a document</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Choose a document from the list to view its pages and evidence locations.
        </p>
      </div>
    );
  }

  if (!document.previewable || !url) {
    return (
      <div className="flex h-[360px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-slate-50 px-6 text-center">
        <FileWarning className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium">No page preview for this document</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          {document.filename
            ? `${document.filename} is a structured data file, not a PDF or image.`
            : "The pipeline did not supply a document file for this record."}{" "}
          The extracted findings and their notes remain available on the right.
        </p>
      </div>
    );
  }

  if (/\.(jpe?g|png|gif|webp|bmp)$/i.test(document.filename ?? "")) {
    return (
      <ImageViewer
        key={document.doc_id}
        url={url}
        docId={document.doc_id}
        findings={findings}
        selectedFindingId={selectedFindingId}
        onSelectFinding={onSelectFinding}
      />
    );
  }

  return (
    <PdfViewerClient
      key={document.doc_id}
      url={url}
      docId={document.doc_id}
      findings={findings}
      selectedFindingId={selectedFindingId}
      onSelectFinding={onSelectFinding}
    />
  );
}
