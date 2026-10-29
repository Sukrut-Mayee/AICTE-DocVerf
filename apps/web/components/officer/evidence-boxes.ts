import type { Finding, Severity } from "@/lib/api";
import { SEVERITY_LABEL } from "@/lib/format";

export interface EvidenceBox {
  key: string;
  findingId: string;
  severity: Severity;
  page: number;
  bbox: number[];
  label: string;
}

export function normalizeBbox(value: unknown): number[] | null {
  if (
    Array.isArray(value) &&
    value.length === 4 &&
    value.every((entry) => typeof entry === "number" && Number.isFinite(entry))
  ) {
    const [x1, y1, x2, y2] = value as number[];
    if (x2 > x1 && y2 > y1) {
      return [
        Math.max(0, Math.min(1, x1)),
        Math.max(0, Math.min(1, y1)),
        Math.max(0, Math.min(1, x2)),
        Math.max(0, Math.min(1, y2)),
      ];
    }
  }
  return null;
}

export function evidenceBoxes(finding: Finding): Array<{ page: number; bbox: number[] }> {
  const boxes: Array<{ page: number; bbox: number[] }> = [];
  const evidence = finding.evidence ?? {};

  const bbox = normalizeBbox(evidence.bbox);
  const page = typeof evidence.page === "number" ? evidence.page : null;
  if (bbox && page) boxes.push({ page, bbox });

  if (Array.isArray(evidence.regions)) {
    for (const region of evidence.regions) {
      if (!region || typeof region !== "object") continue;
      const record = region as Record<string, unknown>;
      const regionBbox = normalizeBbox(record.bbox);
      const regionPage = typeof record.page === "number" ? record.page : null;
      if (regionBbox && regionPage) boxes.push({ page: regionPage, bbox: regionBbox });
    }
  }

  return boxes;
}

export function boxesForPage(findings: Finding[], docId: string, page: number): EvidenceBox[] {
  const boxes: EvidenceBox[] = [];
  for (const finding of findings) {
    for (const [index, claim] of finding.claims.entries()) {
      if (claim.doc_id !== docId || claim.page !== page) continue;
      const bbox = normalizeBbox(claim.bbox);
      if (!bbox) continue;
      boxes.push({
        key: `${finding.finding_id}-claim-${index}`,
        findingId: finding.finding_id,
        severity: finding.severity,
        page,
        bbox,
        label: `${SEVERITY_LABEL[finding.severity]} finding${
          finding.rule_id ? ` · ${finding.rule_id}` : ""
        }: ${finding.message}`,
      });
    }

    if (finding.doc_ids.includes(docId)) {
      for (const [index, box] of evidenceBoxes(finding).entries()) {
        if (box.page !== page) continue;
        boxes.push({
          key: `${finding.finding_id}-evidence-${index}`,
          findingId: finding.finding_id,
          severity: finding.severity,
          page,
          bbox: box.bbox,
          label: `${SEVERITY_LABEL[finding.severity]} evidence: ${finding.message}`,
        });
      }
    }
  }
  return boxes;
}

export function firstPageForFinding(finding: Finding, docId: string): number | null {
  for (const claim of finding.claims) {
    if (claim.doc_id === docId && claim.page && normalizeBbox(claim.bbox)) {
      return claim.page;
    }
  }
  if (finding.doc_ids.includes(docId)) {
    const box = evidenceBoxes(finding)[0];
    if (box) return box.page;
  }
  for (const claim of finding.claims) {
    if (claim.page && normalizeBbox(claim.bbox)) return claim.page;
  }
  return null;
}
