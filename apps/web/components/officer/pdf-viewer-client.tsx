"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, Minus, Plus, Scan } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Finding } from "@/lib/api";
import { SEVERITY_BOX } from "@/lib/format";
import { boxesForPage, firstPageForFinding } from "@/components/officer/evidence-boxes";
import { cn } from "@/lib/utils";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

interface PdfViewerClientProps {
  url: string;
  docId: string;
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

export default function PdfViewerClient({
  url,
  docId,
  findings,
  selectedFindingId,
  onSelectFinding,
}: PdfViewerClientProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [numPages, setNumPages] = useState(1);
  const [pageNumber, setPageNumber] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [pageReady, setPageReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const update = () => setContainerWidth(element.clientWidth);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const selectedFinding = useMemo(
    () => findings.find((finding) => finding.finding_id === selectedFindingId) ?? null,
    [findings, selectedFindingId],
  );
  const focusPage = selectedFinding ? firstPageForFinding(selectedFinding, docId) : null;

  useEffect(() => {
    if (focusPage) setPageNumber(focusPage);
  }, [focusPage]);

  // `clientWidth` includes the viewer padding; subtract it so "Fit" does not
  // introduce a horizontal scrollbar. Keep the page width stable while the
  // vertical scrollbar appears by reserving its gutter in the scroll container.
  const availableWidth = containerWidth > 0 ? containerWidth - 24 : 680;
  const pageWidth = Math.round(Math.max(availableWidth, 240) * zoom);

  useEffect(() => {
    setPageReady(false);
  }, [docId, pageNumber, pageWidth]);

  const boxes = useMemo(
    () => boxesForPage(findings, docId, pageNumber),
    [findings, docId, pageNumber],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-slate-50 px-3 py-2">
        <div className="flex items-center gap-1">
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-8 w-8 bg-white"
            onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
            disabled={pageNumber <= 1}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[92px] text-center text-xs font-medium">
            Page {pageNumber} of {numPages}
          </span>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-8 w-8 bg-white"
            onClick={() => setPageNumber((current) => Math.min(numPages, current + 1))}
            disabled={pageNumber >= numPages}
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-8 w-8 bg-white"
            onClick={() => setZoom((current) => Math.max(0.6, Math.round((current - 0.1) * 10) / 10))}
            disabled={zoom <= 0.6}
            aria-label="Zoom out"
          >
            <Minus className="h-4 w-4" />
          </Button>
          <span className="min-w-[52px] text-center text-xs font-medium">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-8 w-8 bg-white"
            onClick={() => setZoom((current) => Math.min(2, Math.round((current + 0.1) * 10) / 10))}
            disabled={zoom >= 2}
            aria-label="Zoom in"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="ml-1 bg-white"
            onClick={() => setZoom(1)}
          >
            <Scan className="h-3.5 w-3.5" />
            Fit
          </Button>
        </div>
      </div>

      {loadError ? (
        <Alert variant="warning">
          <AlertTitle>The PDF could not be rendered</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{loadError}</p>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-sky-800 underline"
            >
              Open the document directly
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </AlertDescription>
        </Alert>
      ) : (
        <div
          ref={containerRef}
          className="max-h-[70vh] overflow-auto overscroll-contain rounded-lg border bg-slate-100 p-3 [scrollbar-gutter:stable] scrollbar-thin lg:max-h-[calc(100vh-18rem)]"
        >
          <div className="mx-auto w-fit">
            <Document
              file={url}
              onLoadSuccess={(pdf: { numPages: number }) => {
                setNumPages(pdf.numPages);
                setPageNumber((current) => Math.min(current, pdf.numPages));
                setLoadError(null);
              }}
              onLoadError={(error: Error) => setLoadError(error.message)}
              loading={
                <div className="flex h-[420px] w-[min(100%,720px)] items-center justify-center rounded bg-white text-sm text-muted-foreground">
                  Loading document…
                </div>
              }
            >
              <div className="relative" style={{ width: pageWidth }}>
                <Page
                  pageNumber={pageNumber}
                  width={pageWidth}
                  renderTextLayer
                  renderAnnotationLayer={false}
                  onRenderSuccess={() => setPageReady(true)}
                  loading={
                    <div className="flex h-[420px] items-center justify-center rounded bg-white text-sm text-muted-foreground">
                      Rendering page…
                    </div>
                  }
                />
                {pageReady ? (
                  <div className="pointer-events-none absolute inset-0">
                    {boxes.map((box) => {
                      const selected = box.findingId === selectedFindingId;
                      const [x1, y1, x2, y2] = box.bbox;
                      return (
                        <button
                          key={box.key}
                          type="button"
                          data-evidence-box={box.findingId}
                          onClick={() => onSelectFinding(box.findingId)}
                          title={box.label}
                          aria-label={box.label}
                          className={cn(
                            "pointer-events-auto absolute rounded-sm border-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900",
                            SEVERITY_BOX[box.severity],
                            selected && "z-10 ring-2 ring-slate-900/70 ring-offset-1",
                          )}
                          style={{
                            left: `${x1 * 100}%`,
                            top: `${y1 * 100}%`,
                            width: `${Math.max((x2 - x1) * 100, 0.35)}%`,
                            height: `${Math.max((y2 - y1) * 100, 0.25)}%`,
                          }}
                        />
                      );
                    })}
                  </div>
                ) : null}
              </div>
            </Document>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          Coloured boxes mark where the pipeline located evidence on this page. A box
          indicates location, not proof of manipulation.
        </span>
        <span>
          {boxes.length} box{boxes.length === 1 ? "" : "es"} on this page
        </span>
      </div>
    </div>
  );
}
