"""TRD §5.1 enums. Frozen contract: do not change names or values without lead approval."""

from enum import Enum


class DocType(str, Enum):
    APPLICATION_FORM = "application_form"
    LAND_DEED = "land_deed"
    NOC = "noc"
    AFFIDAVIT = "affidavit"
    ACCREDITATION_CERT = "accreditation_cert"
    LAB_PHOTO = "lab_photo"


class Layer(str, Enum):
    A = "A"  # provenance / source verification
    B = "B"  # consistency (graph, history, cross-institution, timeline)
    C = "C"  # template / structure / format
    D = "D"  # pixel forensics + metadata
    E = "E"  # AI-generation signal


class CheckStatus(str, Enum):
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AuthorityTier(str, Enum):
    ISSUER_VERIFIED = "issuer_verified"
    THIRD_PARTY = "third_party"
    SELF_DECLARED = "self_declared"


class VerificationStatus(str, Enum):  # problem statement's six statuses
    VERIFIED = "verified"
    MISMATCH_DETECTED = "mismatch_detected"
    EXPIRED = "expired"
    VERIFICATION_PENDING = "verification_pending"
    SOURCE_UNAVAILABLE = "source_unavailable"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class FindingType(str, Enum):
    ATTRIBUTE_CONFLICT = "attribute_conflict"
    RELATIONSHIP_VIOLATION = "relationship_violation"
    TIMELINE_VIOLATION = "timeline_violation"
    RULE_FAILED = "rule_failed"
    MISSING_DOC = "missing_doc"
    EXPIRED = "expired"
    UNREADABLE = "unreadable"  # low-confidence data; confirm manually
    UNDETERMINED = "undetermined"  # not enough evidence to evaluate
    DUPLICATE = "duplicate"
    FORENSIC_SIGNAL = "forensic_signal"
    PROVENANCE_FAILURE = "provenance_failure"
    SOURCE_MISMATCH = "source_mismatch"


class RuleOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNDETERMINED = "undetermined"


class DocOverallStatus(str, Enum):
    NO_ISSUES = "no_issues"
    FLAGGED = "flagged"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class Decision(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_DEFICIENCIES = "approve_with_deficiencies"
    REQUEST_RECTIFICATION = "request_rectification"
    SITE_INSPECTION = "site_inspection"
    REJECT = "reject"
