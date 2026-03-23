"""Deterministic manuscript generation for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List


StudyInput = Dict[str, Any]
Claim = Dict[str, Any]


REQUIRED_STUDY_KEYS = ("study_id", "title", "domain", "objective")
REQUIRED_FINDING_KEYS = ("finding_id", "claim_text", "evidence_reference_ids", "priority")
ALLOWED_EVIDENCE_NEEDED = (
    "RCT",
    "meta-analysis",
    "systematic review",
    "observational",
    "guideline",
    "conceptual",
)
GENERIC_PATTERNS = (
    "improves outcomes",
    "is beneficial",
    "shows promise",
    "may help",
    "appears effective",
)
TESTABLE_MARKERS = (
    "percent",
    "median",
    "mean",
    "rate",
    "risk",
    "odds",
    "hazard",
    "weeks",
    "months",
    "days",
    "baseline",
    "follow-up",
    "adherence",
    "throughput",
    "score",
)


class InputValidationError(ValueError):
    """Raised when the input payload is not valid."""


def _validate_study(study: Dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_STUDY_KEYS if key not in study]
    if missing:
        raise InputValidationError(f"missing study keys: {missing}")


def _validate_claim_text(finding: Dict[str, Any]) -> None:
    claim_text = finding["claim_text"].strip()
    normalized = claim_text.lower()
    if len(claim_text.split()) < 6:
        raise InputValidationError(
            f"finding {finding['finding_id']} claim_text too short for peer review"
        )
    if any(pattern in normalized for pattern in GENERIC_PATTERNS):
        raise InputValidationError(
            f"finding {finding['finding_id']} claim_text too generic for peer review"
        )
    has_numeric_anchor = bool(re.search(r"\b\d+(?:\.\d+)?\b", claim_text))
    has_testable_marker = any(marker in normalized for marker in TESTABLE_MARKERS)
    if not (has_numeric_anchor or has_testable_marker):
        raise InputValidationError(
            f"finding {finding['finding_id']} claim_text lacks a testable anchor"
        )


def _validate_findings(findings: List[Dict[str, Any]]) -> None:
    if not findings:
        raise InputValidationError("findings must be non-empty")
    for finding in findings:
        missing = [key for key in REQUIRED_FINDING_KEYS if key not in finding]
        if missing:
            raise InputValidationError(
                f"finding {finding.get('finding_id', '<missing>')} missing keys: {missing}"
            )
        if not finding["evidence_reference_ids"]:
            raise InputValidationError(
                f"finding {finding['finding_id']} must include evidence_reference_ids"
            )
        _validate_claim_text(finding)


def _infer_evidence_needed(finding: Dict[str, Any]) -> str:
    claim_text = finding["claim_text"].lower()

    if any(token in claim_text for token in ("guideline", "consensus", "recommend")):
        return "guideline"
    if any(token in claim_text for token in ("meta-analysis", "pooled", "across studies")):
        return "meta-analysis"
    if any(token in claim_text for token in ("systematic review", "reviewed studies")):
        return "systematic review"
    if any(token in claim_text for token in ("mechanism", "pathway", "framework", "conceptual")):
        return "conceptual"
    if any(token in claim_text for token in ("association", "correlated", "predict", "linked")):
        return "observational"
    if finding["priority"] == "primary":
        return "RCT"
    if any(token in claim_text for token in ("adherence", "utilization", "uptake", "pattern")):
        return "observational"
    return "observational"


def _build_justification(evidence_needed: str) -> str:
    reason_map = {
        "RCT": "Intervention effect claims need controlled causal evidence.",
        "meta-analysis": "Cross-study summary claims need pooled quantitative evidence.",
        "systematic review": "Broad evidence synthesis claims need structured literature review.",
        "observational": "Behavior or association claims need real-world follow-up evidence.",
        "guideline": "Practice recommendations need consensus or guideline support.",
        "conceptual": "Mechanistic claims need conceptual or translational rationale.",
    }
    justification = reason_map[evidence_needed]
    if len(justification.split()) <= 20:
        return justification
    return " ".join(justification.split()[:20])


def generate_claims(payload: StudyInput) -> Dict[str, Any]:
    """Generate normalized claims JSON from structured study findings."""
    study = payload.get("study", {})
    findings = payload.get("findings", [])

    _validate_study(study)
    _validate_findings(findings)

    claims: List[Claim] = []
    seen = {}
    deduplicated_findings: List[List[str]] = []

    for finding in findings:
        evidence_needed = _infer_evidence_needed(finding)
        dedupe_key = (
            finding["claim_text"].strip(),
            tuple(finding["evidence_reference_ids"]),
            finding["priority"],
            evidence_needed,
        )
        if dedupe_key in seen:
            seen[dedupe_key]["finding_ids"].append(finding["finding_id"])
            deduplicated_findings.append(seen[dedupe_key]["finding_ids"][:])
            continue

        claim = {
            "claim_id": f"CLM-{len(claims) + 1:03d}",
            "finding_ids": [finding["finding_id"]],
            "text": finding["claim_text"].strip(),
            "priority": finding["priority"],
            "evidence_reference_ids": list(finding["evidence_reference_ids"]),
            "evidence_needed": evidence_needed,
            "justification": _build_justification(evidence_needed),
        }
        claims.append(claim)
        seen[dedupe_key] = claim

    return {
        "study": {key: study[key] for key in REQUIRED_STUDY_KEYS},
        "claims": claims,
        "generation_notes": {
            "claim_count": len(claims),
            "deduplicated_findings": deduplicated_findings,
            "allowed_evidence_needed": list(ALLOWED_EVIDENCE_NEEDED),
        },
    }
