"use client";

import { useMemo, useState } from "react";
import { Minus, Plus, Scan } from "lucide-react";

import { boxesForPage } from "@/components/officer/evidence-boxes";
import { Button } from "@/components/ui/button";
import type { Finding } from "@/lib/api";
import { SEVERITY_BOX } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ImageViewerProps {
  url: string;
  docId: string;
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

export function ImageViewer({
  url,
  docId,
  findings,
  selectedFindingId,
  onSelectFinding,
}: ImageViewerProps) {
  const [zoom, setZoom] = useState(1);
  const [failed, setFailed] = useState(false);
  // A photo is a single page; findings on it carry page 1 (or no page).
  const boxes = useMemo(() => boxesForPage(findings, docId, 1), [findings, docId]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-1 rounded-lg border bg-slate-50 px-3 py-2">
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="h-8 w-8 bg-white"
          onClick={() => setZoom((z) => Math.max(0.5, Math.round((z - 0.25) * 100) / 100))}
          disabled={zoom <= 0.5}
          aria-label="Zoom out"
        >
          <Minus className="h-4 w-4" />
        </Button>
        <span className="min-w-[52px] text-center text-xs font-medium">{Math.round(zoom * 100)}%</span>
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="h-8 w-8 bg-white"
          onClick={() => setZoom((z) => Math.min(3, Math.round((z + 0.25) * 100) / 100))}
          disabled={zoom >= 3}
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

      {failed ? (
        <p className="rounded-lg border bg-amber-50 p-3 text-sm">
          The image could not be loaded.{" "}
          <a href={url} target="_blank" rel="noreferrer" className="font-medium underline">
            Open it directly
          </a>
        </p>
      ) : (
        <div className="max-h-[70vh] overflow-auto overscroll-contain rounded-lg border bg-slate-100 p-3 [scrollbar-gutter:stable] scrollbar-thin lg:max-h-[calc(100vh-18rem)]">
          {/* Zoom 100% = fit to the panel width; larger values scroll. */}
          <div className="relative mx-auto" style={{ width: `${zoom * 100}%` }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt={`Document ${docId}`}
              className="block h-auto w-full rounded bg-white"
              onError={() => setFailed(true)}
            />
            <div className="pointer-events-none absolute inset-0">
              {boxes.map((box) => {
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
                      box.findingId === selectedFindingId &&
                        "z-10 ring-2 ring-slate-900/70 ring-offset-1",
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
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          Coloured boxes mark where the pipeline located evidence. A box indicates location,
          not proof of manipulation.
        </span>
        <span>
          {boxes.length} box{boxes.length === 1 ? "" : "es"} on this image
        </span>
      </div>
    </div>
  );
}
