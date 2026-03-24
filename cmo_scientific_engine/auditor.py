"""Audit logic for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


Failure = Dict[str, str]
CLAIM_ID_PATTERN = re.compile(r"^CLM-\d{3}$")
REFERENCE_ID_PATTERN = re.compile(r"^REF-\d{3}$")
ACCEPTABLE_EVIDENCE = {"HIGH", "MODERATE"}
WEAK_EVIDENCE = {"LOW"}
CAUSAL_PATTERNS = (
    r"\bcauses?\b",
    r"\bcaused\b",
    r"\bimproves?\b",
    r"\bimproved\b",
    r"\bprevents?\b",
    r"\bprevented\b",
    r"\breduces?\b",
    r"\breduced\b",
    r"\bdecreases?\b",
    r"\bdecreased\b",
    r"\bincreases?\b",
    r"\bincreased\b",
    r"\beliminates?\b",
    r"\bproves?\b",
)


def _percent(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 1)


def _normalize_verification_status(status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized in {"VERIFIED", "UNVERIFIED", "FAILED"}:
        return normalized
    return "UNVERIFIED"


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


def _has_minimum_low_bias_inputs(methodology: Dict[str, bool]) -> bool:
    return all(
        methodology[field]
        for field in ("confidence_interval", "sample_size_justification", "comparator")
    )


def _citation_supports_rct(citation: str) -> bool:
    normalized = citation.lower()
    return any(token in normalized for token in ("randomized", "randomised", "controlled trial", "trial", "placebo"))


def _has_causal_language(text: str) -> bool:
    normalized = text.lower()
    if "was associated with" in normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in CAUSAL_PATTERNS)


def _confirmed_rct(study: Dict[str, Any], mapping: Dict[str, Any]) -> bool:
    design_text = " ".join(
        str(study.get(key, "")).lower() for key in ("design", "design_details", "study_design")
    )
    study_confirms_rct = any(token in design_text for token in ("randomized", "randomised", "rct", "controlled trial"))
    citations = mapping.get("citations", [])
    statuses = [_normalize_verification_status(status) for status in mapping.get("reference_verification_status", [])]
    matches = mapping.get("evidence_match", [])

    for citation, status, match in zip(citations, statuses, matches):
        if status == "VERIFIED" and match in ACCEPTABLE_EVIDENCE and _citation_supports_rct(citation):
            return True
    return study_confirms_rct and any(status == "VERIFIED" for status in statuses)


def _risk_of_bias(
    claim: Dict[str, Any],
    best_match: str | None,
    methodology: Dict[str, bool],
    verified_references_present: bool,
) -> str:
    evidence_needed = claim.get("evidence_needed", "observational")
    if best_match is None or not verified_references_present:
        return "HIGH"
    if not _has_minimum_low_bias_inputs(methodology):
        return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"
    if evidence_needed == "RCT":
        return "LOW" if best_match == "HIGH" and methodology["design_details"] else "MODERATE"
    if evidence_needed in {"meta-analysis", "systematic review"}:
        return "MODERATE"
    if evidence_needed == "conceptual":
        return "MODERATE"
    return "MODERATE" if best_match in {"HIGH", "MODERATE"} else "HIGH"


def _support_confidence(
    best_match: str | None,
    verification_statuses: List[str],
    methodology: Dict[str, bool],
) -> str:
    normalized_statuses = [_normalize_verification_status(status) for status in verification_statuses]
    if not normalized_statuses or "FAILED" in normalized_statuses:
        return "LOW"
    method_complete = all(methodology.values())
    if all(status == "UNVERIFIED" for status in normalized_statuses):
        return "UNCERTAIN"
    if best_match == "HIGH" and method_complete and all(status == "VERIFIED" for status in normalized_statuses):
        return "HIGH"
    if best_match in {"HIGH", "MODERATE"} and all(status == "VERIFIED" for status in normalized_statuses):
        return "MODERATE" if method_complete else "UNCERTAIN"
    if best_match == "MODERATE":
        return "UNCERTAIN"
    return "LOW"


def _rewrite_claim_text(text: str) -> str:
    replacements = (
        (r"\bimproved\b", "was associated with improvement in"),
        (r"\bimproves\b", "was associated with improvement in"),
        (r"\bincreased\b", "was associated with an increase in"),
        (r"\bincreases\b", "was associated with an increase in"),
        (r"\breduced\b", "was associated with a reduction in"),
        (r"\breduces\b", "was associated with a reduction in"),
        (r"\bdecreased\b", "was associated with a decrease in"),
        (r"\bdecreases\b", "was associated with a decrease in"),
        (r"\bprevented\b", "was associated with lower"),
        (r"\bprevents\b", "was associated with lower"),
        (r"\bcaused\b", "was associated with"),
        (r"\bcauses\b", "was associated with"),
    )
    revised = text
    for pattern, replacement in replacements:
        revised, count = re.subn(pattern, replacement, revised, count=1, flags=re.IGNORECASE)
        if count:
            return revised
    if "was associated with" in revised.lower():
        return revised
    return f"was associated with {revised[0].lower()}{revised[1:]}" if revised else revised


def _is_overclaiming(claim: Dict[str, Any], confirmed_rct: bool) -> str:
    return "YES" if _has_causal_language(claim.get("text", "")) and not confirmed_rct else "NO"


def _scientific_reliability_score(claim_flags: List[Dict[str, bool]]) -> float:
    if not claim_flags:
        return 0.0
    base_score = 100.0
    if any(flags["has_unverified_reference"] for flags in claim_flags):
        base_score -= 30.0
    if any(flags["missing_methodological_data"] for flags in claim_flags):
        base_score -= 20.0
    if any(flags["causal_without_confirmed_rct"] for flags in claim_flags):
        base_score -= 20.0
    if any(flags["has_failed_reference"] for flags in claim_flags):
        base_score -= 20.0
    reliability_score = max(0.0, round(base_score, 1))
    if any(flags["non_verified_reference_present"] for flags in claim_flags):
        reliability_score = min(reliability_score, 50.0)
    return reliability_score


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
    claim_flags: List[Dict[str, bool]] = []
    rewritten_claims: List[Dict[str, str]] = []

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
                "reference_verification_status": [],
                "citations": [],
            },
        )
        mapped_reference_ids = mapping.get("reference_ids", [])
        evidence_matches = mapping.get("evidence_match", [])
        mismatch_flags = mapping.get("mismatch_flags", [])
        verification_statuses = [_normalize_verification_status(status) for status in mapping.get("reference_verification_status", [])]
        best_match = _best_match(evidence_matches)
        methodology = _methodology_completeness(study, claim)
        confirmed_rct = _confirmed_rct(study, mapping)
        causal_language = _has_causal_language(claim.get("text", ""))
        rewritten_claim_text = claim.get("text", "")

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
            and all(status == "VERIFIED" for status in verification_statuses)
            else "NO"
        )
        direct_support = "YES" if mapped_reference_ids else "NO"
        verified_references_present = any(status == "VERIFIED" for status in verification_statuses)
        risk_of_bias = _risk_of_bias(claim, best_match, methodology, verified_references_present)
        overclaiming = _is_overclaiming(claim, confirmed_rct)
        weak_support = (
            (not mapped_reference_ids)
            or best_match in WEAK_EVIDENCE
            or best_match is None
            or support_confidence in {"LOW", "UNCERTAIN"}
        )

        if weak_support:
            weak_claim_count += 1
        if "UNVERIFIED" in verification_statuses:
            checks.append("reference_verification_incomplete")
            failed_checks.append(
                {
                    "claim_id": claim_id,
                    "code": "reference_unverified",
                    "detail": "reference_metadata_insufficient_for_independent_verification",
                    "severity": "warning",
                }
            )
        if "FAILED" in verification_statuses or "reference_verification_failed" in mismatch_flags:
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
            checks.append("overclaiming_detected")
            rewritten_claim_text = _rewrite_claim_text(claim.get("text", ""))
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

        claim_flags.append(
            {
                "has_unverified_reference": "UNVERIFIED" in verification_statuses,
                "missing_methodological_data": bool(missing_method_fields),
                "causal_without_confirmed_rct": causal_language and not confirmed_rct,
                "has_failed_reference": "FAILED" in verification_statuses,
                "non_verified_reference_present": any(status != "VERIFIED" for status in verification_statuses),
            }
        )
        rewritten_claims.append({"claim_id": claim_id, "text": rewritten_claim_text})
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
                "reference_verification_status": verification_statuses,
                "confirmed_rct": "YES" if confirmed_rct else "NO",
                "rewritten_claim_text": rewritten_claim_text,
            }
        )

    weak_support_pct = _percent(weak_claim_count, len(claim_audits))
    high_quality_pct = _percent(high_quality_claim_count, len(claim_audits))
    reliability_score = _scientific_reliability_score(claim_flags)

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
        "rewritten_claims": rewritten_claims,
    }
