import { Badge } from "@/components/ui/badge";
import type {
  DecisionType,
  FindingActionType,
  OverallStatus,
  Severity,
  VerificationStatus,
} from "@/lib/api";
import {
  ACTION_LABEL,
  DECISION_BADGE,
  DECISION_LABEL,
  OVERALL_BADGE,
  OVERALL_LABEL,
  SEVERITY_BADGE,
  SEVERITY_LABEL,
  VERIFICATION_LABEL,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={cn("capitalize", SEVERITY_BADGE[severity])}>
      {SEVERITY_LABEL[severity]}
    </Badge>
  );
}

export function OverallBadge({ overall }: { overall: OverallStatus }) {
  return (
    <Badge variant="outline" className={cn(OVERALL_BADGE[overall])}>
      {OVERALL_LABEL[overall]}
    </Badge>
  );
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  return (
    <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-600">
      {VERIFICATION_LABEL[status]}
    </Badge>
  );
}

export function DecisionBadge({ decision }: { decision: DecisionType }) {
  return (
    <Badge variant="outline" className={cn(DECISION_BADGE[decision])}>
      {DECISION_LABEL[decision]}
    </Badge>
  );
}

export function ActionBadge({ action }: { action: FindingActionType }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        action === "confirm"
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-slate-300 bg-slate-100 text-slate-700",
      )}
    >
      {ACTION_LABEL[action]}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: "review_pending" | "decided" }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        status === "decided"
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-amber-200 bg-amber-50 text-amber-800",
      )}
    >
      {status === "decided" ? "Decision recorded" : "Review pending"}
    </Badge>
  );
}
