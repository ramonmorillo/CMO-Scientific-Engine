"""Audit logic for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


Failure = Dict[str, str]
CLAIM_ID_PATTERN = re.compile(r"^CLM-\d{3}$")
REFERENCE_ID_PATTERN = re.compile(r"^REF-\d{3}$")
ACCEPTABLE_EVIDENCE = {"HIGH", "MODERATE"}
WEAK_EVIDENCE = {"LOW"}
CAUSAL_MARKERS = ("caused", "proved", "eliminated", "prevented", "improved", "increased", "reduced", "decreased")


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


def _methodology_completeness(study: Dict[str, Any], claim: Dict[str, Any]) -> Dict[str, bool]:
    design_present = any(str(study.get(key, "")).strip() for key in ("design", "design_details", "study_design"))
    comparator_present = bool(str(study.get("comparator", "")).strip())
    sample_size_present = bool(str(study.get("sample_size_justification", "")).strip())
    confidence_interval_present = any(
        bool(str(study.get(key, "")).strip()) for key in ("confidence_interval", "confidence_intervals")
    )
    uncertainty_present = bool(str(claim.get("uncertainty", "")).strip())
    return {
        "design_details": design_present,
        "comparator": comparator_present,
        "sample_size_justification": sample_size_present,
        "confidence_interval": confidence_interval_present,
        "uncertainty": uncertainty_present,
    }


def _risk_of_bias(claim: Dict[str, Any], best_match: str | None, methodology: Dict[str, bool]) -> str:
    evidence_needed = claim.get("evidence_needed", "observational")
    method_complete = all(methodology.values())
    if best_match is None:
        return "HIGH"
    if evidence_needed == "RCT":
        if not method_complete:
            return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"
        return "LOW" if best_match == "HIGH" else "MODERATE"
    if evidence_needed in {"meta-analysis", "systematic review"}:
        return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"
    if evidence_needed == "conceptual":
        return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"
    return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"


def _support_confidence(
    best_match: str | None,
    verification_statuses: List[str],
    methodology: Dict[str, bool],
) -> str:
    if not verification_statuses or "failed" in verification_statuses:
        return "LOW"
    method_complete = all(methodology.values())
    if all(status == "unverified" for status in verification_statuses):
        return "UNCERTAIN"
    if best_match == "HIGH" and method_complete and all(status == "verified" for status in verification_statuses):
        return "HIGH"
    if best_match in {"HIGH", "MODERATE"}:
        return "MODERATE" if method_complete else "UNCERTAIN"
    return "LOW"


def _is_overclaiming(
    claim: Dict[str, Any],
    best_match: str | None,
    study: Dict[str, Any],
    methodology: Dict[str, bool],
) -> str:
    text = claim.get("text", "").lower()
    design_text = " ".join(
        str(study.get(key, "")).lower() for key in ("design", "design_details", "study_design")
    )
    randomized_design = any(token in design_text for token in ("randomized", "randomised", "rct"))
    complete_design = methodology["design_details"]
    if any(marker in text for marker in CAUSAL_MARKERS) and (not randomized_design or not complete_design):
        return "POSSIBLE"
    if any(marker in text for marker in CAUSAL_MARKERS) and claim.get("evidence_needed") != "RCT":
        return "YES"
    if any(marker in text for marker in CAUSAL_MARKERS) and best_match != "HIGH":
        return "YES"
    return "NO"


def audit_claims(claims_json: Dict[str, Any], mapping_json: Dict[str, Any]) -> Dict[str, Any]:
    """Audit claim-to-reference consistency and scientific support."""
    claims = claims_json.get("claims", [])
    study = claims_json.get("study", {})
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
            len(mapping.get("reference_verification_status", [])),
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
        verification_statuses = mapping.get("reference_verification_status", [])
        best_match = _best_match(evidence_matches)
        methodology = _methodology_completeness(study, claim)

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
        elif best_match == "MODERATE":
            checks.append("scientific_support_moderate")
        else:
            checks.append("scientific_support_low")

        support_confidence = _support_confidence(best_match, verification_statuses, methodology)
        if best_match == "HIGH" and support_confidence == "HIGH":
            high_quality_claim_count += 1

        evidence_level_ok = (
            "YES"
            if best_match in ACCEPTABLE_EVIDENCE
            and support_confidence in {"HIGH", "MODERATE"}
            and "failed" not in verification_statuses
            else "NO"
        )
        direct_support = "YES" if mapped_reference_ids else "NO"
        risk_of_bias = _risk_of_bias(claim, best_match, methodology)
        overclaiming = _is_overclaiming(claim, best_match, study, methodology)
        weak_support = (
            (not mapped_reference_ids)
            or best_match in WEAK_EVIDENCE
            or best_match is None
            or support_confidence in {"LOW", "UNCERTAIN"}
        )

        if weak_support:
            weak_claim_count += 1
        if "reference_unverified" in mismatch_flags:
            checks.append("reference_verification_incomplete")
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "reference_unverified",
                    "detail": "reference_metadata_insufficient_for_independent_verification",
                    "severity": "warning",
                }
            )
        if "reference_verification_failed" in mismatch_flags or "failed" in verification_statuses:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "reference_verification_failed",
                    "detail": "reference_metadata_not_verifiable",
                    "severity": "fail",
                }
            )
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
        missing_method_fields = [name for name, present in methodology.items() if not present]
        if missing_method_fields:
            checks.append("methodology_incomplete")
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "methodology_incomplete",
                    "detail": "missing_" + "_".join(missing_method_fields),
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
        if overclaiming == "POSSIBLE":
            checks.append("causal_language_not_confirmed")
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "possible_overclaiming",
                    "detail": "causal_language_not_supported_by_design_details",
                    "severity": "warning",
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
                "support_confidence": support_confidence,
            }
        )

    weak_support_pct = _percent(weak_claim_count, len(claim_audits))
    high_quality_pct = _percent(high_quality_claim_count, len(claim_audits))
    fail_count = len([f for f in failed_checks if f["severity"] == "fail"])
    warning_count = len([f for f in failed_checks if f["severity"] == "warning"])
    methodology_incomplete = any(not all(_methodology_completeness(study, claim).values()) for claim in claims)
    has_unverified_reference = any(
        "unverified" in mapping.get("reference_verification_status", []) for mapping in mappings
    )
    reliability_score = max(
        0.0,
        round(100 - (weak_support_pct * 0.7) - (fail_count * 8) - (warning_count * 2), 1),
    )
    if has_unverified_reference:
        reliability_score = min(reliability_score, 60.0)
    if methodology_incomplete:
        reliability_score = min(reliability_score, 40.0)

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
