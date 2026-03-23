"""Deterministic manuscript generation for the CMO Scientific Engine."""

from __future__ import annotations

from typing import Any, Dict, List


StudyInput = Dict[str, Any]
Claim = Dict[str, Any]


REQUIRED_STUDY_KEYS = ("study_id", "title", "domain", "objective")
REQUIRED_FINDING_KEYS = ("finding_id", "claim_text", "evidence_reference_ids", "priority")


class InputValidationError(ValueError):
    """Raised when the input payload is not valid."""


def _validate_study(study: Dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_STUDY_KEYS if key not in study]
    if missing:
        raise InputValidationError(f"missing study keys: {missing}")


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
        dedupe_key = (
            finding["claim_text"].strip(),
            tuple(finding["evidence_reference_ids"]),
            finding["priority"],
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
        }
        claims.append(claim)
        seen[dedupe_key] = claim

    return {
        "study": {key: study[key] for key in REQUIRED_STUDY_KEYS},
        "claims": claims,
        "generation_notes": {
            "claim_count": len(claims),
            "deduplicated_findings": deduplicated_findings,
        },
    }
