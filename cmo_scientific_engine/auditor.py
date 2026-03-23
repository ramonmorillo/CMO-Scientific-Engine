"""Audit logic for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


Failure = Dict[str, str]
CLAIM_ID_PATTERN = re.compile(r"^CLM-\d{3}$")
REFERENCE_ID_PATTERN = re.compile(r"^REF-\d{3}$")
HIGH_QUALITY_EVIDENCE = {"HIGH"}
ACCEPTABLE_EVIDENCE = {"HIGH", "MODERATE"}
WEAK_EVIDENCE = {"LOW"}


def _percent(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 1)


def _best_match(matches: List[str]) -> str | None:
    if "HIGH" in matches:
        return "HIGH"
    if "MODERATE" in matches:
        return "MODERATE"
    if "LOW" in matches:
        return "LOW"
    return None


def _risk_of_bias(claim: Dict[str, Any], best_match: str | None) -> str:
    evidence_needed = claim.get("evidence_needed", "observational")
    if best_match is None:
        return "HIGH"
    if evidence_needed == "RCT":
        return "LOW" if best_match == "HIGH" else "MODERATE"
    if evidence_needed in {"meta-analysis", "systematic review"}:
        return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"
    if evidence_needed == "conceptual":
        return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"
    return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"


def _is_overclaiming(claim: Dict[str, Any], best_match: str | None) -> str:
    text = claim.get("text", "").lower()
    causal_markers = ("caused", "proved", "eliminated", "prevented")
    if any(marker in text for marker in causal_markers) and claim.get("evidence_needed") != "RCT":
        return "YES"
    if any(marker in text for marker in causal_markers) and best_match != "HIGH":
        return "YES"
    return "NO"


def audit_claims(claims_json: Dict[str, Any], mapping_json: Dict[str, Any]) -> Dict[str, Any]:
    """Audit claim-to-reference consistency and scientific support."""
    claims = claims_json.get("claims", [])
    mappings = mapping_json.get("claim_reference_map", [])
    claim_ids = [claim["claim_id"] for claim in claims]
    claim_id_set = set(claim_ids)
    mappings_by_id = {mapping["claim_id"]: mapping for mapping in mappings}

    failed_checks: List[Failure] = []
    claim_audits = []
    weak_claim_count = 0
    high_quality_claim_count = 0

    seen_claim_ids: Set[str] = set()
    for claim_id in claim_ids:
        if claim_id in seen_claim_ids:
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "duplicate_claim_id",
                    "detail": "claim_id_not_unique",
                    "severity": "fail",
                }
            )
        seen_claim_ids.add(claim_id)
        if not CLAIM_ID_PATTERN.match(claim_id):
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "claim_id_integrity",
                    "detail": "claim_id_format_invalid",
                    "severity": "fail",
                }
            )

    for mapping in mappings:
        mapping_claim_id = mapping["claim_id"]
        if mapping_claim_id not in claim_id_set:
            failed_checks.append(
                {
                    "claim_id": mapping_claim_id,
                    "code": "unknown_claim_id",
                    "detail": "mapping_claim_missing_from_claims_json",
                    "severity": "fail",
                }
            )
        aligned_lengths = {
            len(mapping.get("reference_ids", [])),
            len(mapping.get("citations", [])),
            len(mapping.get("evidence_match", [])),
            len(mapping.get("mismatch_flags", [])),
        }
        if len(aligned_lengths) != 1:
            failed_checks.append(
                {
                    "claim_id": mapping_claim_id,
                    "code": "mapping_alignment",
                    "detail": "mapping_arrays_length_mismatch",
                    "severity": "fail",
                }
            )
        for reference_id in mapping.get("reference_ids", []):
            if not REFERENCE_ID_PATTERN.match(reference_id):
                failed_checks.append(
                    {
                        "claim_id": mapping_claim_id,
                        "code": "reference_id_integrity",
                        "detail": "reference_id_format_invalid",
                        "severity": "fail",
                    }
                )

    for claim in claims:
        claim_id = claim["claim_id"]
        checks = []
        status = "pass"
        mapping = mappings_by_id.get(
            claim_id,
            {
                "reference_ids": [],
                "evidence_match": [],
                "mismatch_flags": [],
            },
        )
        mapped_reference_ids = mapping.get("reference_ids", [])
        evidence_matches = mapping.get("evidence_match", [])
        mismatch_flags = mapping.get("mismatch_flags", [])
        best_match = _best_match(evidence_matches)

        if claim.get("finding_ids"):
            checks.append("has_findings")
        else:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "missing_findings",
                    "detail": "claim_has_no_finding_ids",
                    "severity": "fail",
                }
            )

        if mapped_reference_ids:
            checks.append("has_references")
            checks.append("references_mapped_from_finding_overlap")
        else:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "missing_references",
                    "detail": "claim_has_no_mapped_references",
                    "severity": "fail",
                }
            )

        if best_match == "HIGH":
            checks.append("scientific_support_high")
            high_quality_claim_count += 1
        elif best_match == "MODERATE":
            checks.append("scientific_support_moderate")
        else:
            checks.append("scientific_support_low")

        evidence_level_ok = "YES" if best_match in ACCEPTABLE_EVIDENCE else "NO"
        direct_support = "YES" if mapped_reference_ids else "NO"
        risk_of_bias = _risk_of_bias(claim, best_match)
        overclaiming = _is_overclaiming(claim, best_match)
        weak_support = (not mapped_reference_ids) or best_match in WEAK_EVIDENCE or best_match is None

        if weak_support:
            weak_claim_count += 1
        if "partial_evidence_alignment" in mismatch_flags:
            checks.append("support_gap_warning")
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "partial_evidence_alignment",
                    "detail": "mapped_reference_partially_matches_needed_evidence",
                    "severity": "warning",
                }
            )
        if "evidence_needed_mismatch" in mismatch_flags:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "evidence_mismatch",
                    "detail": "mapped_reference_evidence_weaker_than_required",
                    "severity": "fail",
                }
            )
        if overclaiming == "YES":
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "overclaiming",
                    "detail": "claim_strength_exceeds_support",
                    "severity": "fail",
                }
            )
        if evidence_level_ok == "NO":
            status = "fail"

        claim_audits.append(
            {
                "claim_id": claim_id,
                "status": status,
                "checks": checks,
                "evidence_level_ok": evidence_level_ok,
                "direct_support": direct_support,
                "risk_of_bias": risk_of_bias,
                "overclaiming": overclaiming,
            }
        )

    weak_support_pct = _percent(weak_claim_count, len(claim_audits))
    high_quality_pct = _percent(high_quality_claim_count, len(claim_audits))
    fail_count = len([f for f in failed_checks if f["severity"] == "fail"])
    warning_count = len([f for f in failed_checks if f["severity"] == "warning"])
    reliability_score = max(
        0.0,
        round(100 - (weak_support_pct * 0.7) - (fail_count * 8) - (warning_count * 2), 1),
    )

    if weak_support_pct > 30.0:
        failed_checks.append(
            {
                "claim_id": "GLOBAL",
                "code": "weak_support_threshold",
                "detail": "weakly_supported_claims_exceed_30_percent",
                "severity": "fail",
            }
        )

    passed_claims = sum(1 for audit in claim_audits if audit["status"] == "pass")
    failed_claims = len(claim_audits) - passed_claims

    return {
        "audit_summary": {
            "total_claims": len(claim_audits),
            "passed_claims": passed_claims,
            "failed_claims": failed_claims,
            "high_quality_evidence_pct": high_quality_pct,
            "weakly_supported_pct": weak_support_pct,
            "scientific_reliability_score": reliability_score,
        },
        "claim_audits": claim_audits,
        "failed_checks": failed_checks,
    }
