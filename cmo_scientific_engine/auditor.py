"""Audit logic for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


Failure = Dict[str, str]
CLAIM_ID_PATTERN = re.compile(r"^CLM-\d{3}$")
REFERENCE_ID_PATTERN = re.compile(r"^REF-\d{3}$")
HIGH_QUALITY_EVIDENCE = {"HIGH"}
WEAK_EVIDENCE = {"LOW"}


def _percent(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 1)


def _risk_of_bias(claim: Dict[str, Any], matches: List[str]) -> str:
    evidence_needed = claim.get("evidence_needed", "observational")
    if not matches:
        return "HIGH"
    if evidence_needed == "RCT" and all(match == "HIGH" for match in matches):
        return "LOW"
    if any(match == "LOW" for match in matches):
        return "HIGH"
    if evidence_needed in {"meta-analysis", "systematic review"} and any(
        match == "MODERATE" for match in matches
    ):
        return "MODERATE"
    return "MODERATE" if evidence_needed == "observational" else "LOW"


def _is_overclaiming(claim: Dict[str, Any], matches: List[str]) -> str:
    text = claim.get("text", "").lower()
    causal_markers = ("caused", "proved", "eliminated", "prevented")
    if any(marker in text for marker in causal_markers) and claim.get("evidence_needed") != "RCT":
        return "YES"
    if matches and all(match == "LOW" for match in matches):
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
    orphan_reference_ids: Set[str] = set()

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

    expected_reference_ids = {
        reference_id
        for claim in claims
        for reference_id in claim.get("evidence_reference_ids", [])
    }

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
            if reference_id not in expected_reference_ids:
                orphan_reference_ids.add(reference_id)

    for reference_id in sorted(orphan_reference_ids):
        failed_checks.append(
            {
                "claim_id": "GLOBAL",
                "code": "orphan_reference",
                "detail": f"orphan_reference_id:{reference_id}",
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

        expected_reference_ids_for_claim = set(claim.get("evidence_reference_ids", []))
        mapped_reference_ids_set = set(mapped_reference_ids)
        if mapped_reference_ids_set and mapped_reference_ids_set.issubset(expected_reference_ids_for_claim):
            checks.append("reference_ids_match_evidence_ids")
        else:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "reference_mismatch",
                    "detail": "mapped_reference_ids_not_subset_of_evidence_reference_ids",
                    "severity": "fail",
                }
            )

        evidence_level_ok = "YES" if mapped_reference_ids and all(
            match in {"HIGH", "MODERATE"} for match in evidence_matches
        ) else "NO"
        direct_support = "YES" if mapped_reference_ids_set == expected_reference_ids_for_claim else "NO"
        risk_of_bias = _risk_of_bias(claim, evidence_matches)
        overclaiming = _is_overclaiming(claim, evidence_matches)
        weak_support = (not mapped_reference_ids) or any(match in WEAK_EVIDENCE for match in evidence_matches)

        if evidence_matches and all(match in HIGH_QUALITY_EVIDENCE for match in evidence_matches):
            high_quality_claim_count += 1
        if weak_support:
            weak_claim_count += 1
        if "evidence_needed_mismatch" in mismatch_flags:
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "evidence_mismatch",
                    "detail": "mapped_reference_evidence_weaker_than_required",
                    "severity": "warning",
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
    reliability_score = max(
        0,
        round(
            100
            - (weak_support_pct * 0.7)
            - (len([f for f in failed_checks if f["severity"] == "fail"]) * 8)
            - (len([f for f in failed_checks if f["severity"] == "warning"]) * 2),
            1,
        ),
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
