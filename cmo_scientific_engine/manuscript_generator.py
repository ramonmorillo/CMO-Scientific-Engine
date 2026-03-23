"""Deterministic manuscript generation for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List


StudyInput = Dict[str, Any]
Claim = Dict[str, Any]


REQUIRED_STUDY_KEYS = ("study_id", "title", "domain", "objective")
REQUIRED_FINDING_KEYS = ("finding_id", "raw_result", "uncertainty", "priority")
FORBIDDEN_FINDING_KEYS = ("claim_text", "evidence_reference_ids")
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
PRIORITY_VALUES = {"primary", "secondary"}


class InputValidationError(ValueError):
    """Raised when the input payload is not valid."""


def _validate_study(study: Dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_STUDY_KEYS if key not in study]
    if missing:
        raise InputValidationError(f"missing study keys: {missing}")


def _finding_text(finding: Dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", finding["raw_result"].strip())


def _normalized_uncertainty(finding: Dict[str, Any]) -> str:
    return finding["uncertainty"].strip().lower()


def _validate_finding_text(finding: Dict[str, Any]) -> None:
    raw_result = _finding_text(finding)
    normalized = raw_result.lower()
    if len(raw_result.split()) < 6:
        raise InputValidationError(
            f"finding {finding['finding_id']} raw_result too short for peer review"
        )
    if any(pattern in normalized for pattern in GENERIC_PATTERNS):
        raise InputValidationError(
            f"finding {finding['finding_id']} raw_result too generic for peer review"
        )
    has_numeric_anchor = bool(re.search(r"\b\d+(?:\.\d+)?\b", raw_result))
    has_testable_marker = any(marker in normalized for marker in TESTABLE_MARKERS)
    if not (has_numeric_anchor or has_testable_marker):
        raise InputValidationError(
            f"finding {finding['finding_id']} raw_result lacks a testable anchor"
        )


def _validate_findings(findings: List[Dict[str, Any]]) -> None:
    if not findings:
        raise InputValidationError("findings must be non-empty")

    seen_finding_ids = set()
    for finding in findings:
        missing = [key for key in REQUIRED_FINDING_KEYS if key not in finding]
        if missing:
            raise InputValidationError(
                f"finding {finding.get('finding_id', '<missing>')} missing keys: {missing}"
            )
        forbidden = [key for key in FORBIDDEN_FINDING_KEYS if key in finding]
        if forbidden:
            raise InputValidationError(
                f"finding {finding['finding_id']} contains deprecated keys: {forbidden}"
            )
        if finding["finding_id"] in seen_finding_ids:
            raise InputValidationError(f"duplicate finding_id: {finding['finding_id']}")
        seen_finding_ids.add(finding["finding_id"])
        if _normalized_uncertainty(finding) not in {"low", "moderate", "high", "substantial", "exploratory"}:
            raise InputValidationError(
                f"finding {finding['finding_id']} uncertainty not supported"
            )
        if finding["priority"] not in PRIORITY_VALUES:
            raise InputValidationError(
                f"finding {finding['finding_id']} priority invalid"
            )
        _validate_finding_text(finding)


def _infer_evidence_needed(finding: Dict[str, Any]) -> str:
    result_text = _finding_text(finding).lower()
    uncertainty = _normalized_uncertainty(finding)
    combined = f"{result_text} {uncertainty}"

    if any(token in combined for token in ("guideline", "consensus", "recommend")):
        return "guideline"
    if any(token in combined for token in ("meta-analysis", "pooled", "across studies")):
        return "meta-analysis"
    if any(token in combined for token in ("systematic review", "reviewed studies")):
        return "systematic review"
    if any(token in combined for token in ("mechanism", "pathway", "framework", "conceptual")):
        return "conceptual"
    if any(token in combined for token in ("association", "correlated", "predict", "linked")):
        return "observational"
    if finding["priority"] == "primary" and uncertainty not in {"high", "substantial", "exploratory"}:
        return "RCT"
    if any(token in combined for token in ("adherence", "utilization", "uptake", "pattern")):
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
            _finding_text(finding),
            _normalized_uncertainty(finding),
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
            "text": _finding_text(finding),
            "priority": finding["priority"],
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
