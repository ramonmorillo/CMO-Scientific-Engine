"""Audit logic for the CMO Scientific Engine."""

from __future__ import annotations

from typing import Any, Dict, List


Failure = Dict[str, str]


def audit_claims(claims_json: Dict[str, Any], mapping_json: Dict[str, Any]) -> Dict[str, Any]:
    """Audit claim-to-reference consistency."""
    claims = claims_json.get("claims", [])
    mappings = mapping_json.get("claim_reference_map", [])
    claim_ids = {claim["claim_id"] for claim in claims}
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    mappings_by_id = {mapping["claim_id"]: mapping for mapping in mappings}

    failed_checks: List[Failure] = []
    claim_audits = []

    for mapping in mappings:
        if mapping["claim_id"] not in claim_ids:
            failed_checks.append(
                {
                    "claim_id": mapping["claim_id"],
                    "code": "unknown_claim_id",
                    "detail": "mapping_claim_missing_from_claims_json",
                }
            )

    for claim in claims:
        checks = []
        status = "pass"
        mapping = mappings_by_id.get(claim["claim_id"], {"reference_ids": []})

        if claim.get("finding_ids"):
            checks.append("has_findings")
        else:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim["claim_id"],
                    "code": "missing_findings",
                    "detail": "claim_has_no_finding_ids",
                }
            )

        if mapping.get("reference_ids"):
            checks.append("has_references")
        else:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim["claim_id"],
                    "code": "missing_references",
                    "detail": "claim_has_no_mapped_references",
                }
            )

        expected_reference_ids = set(claim.get("evidence_reference_ids", []))
        mapped_reference_ids = set(mapping.get("reference_ids", []))
        if mapped_reference_ids and mapped_reference_ids.issubset(expected_reference_ids):
            checks.append("reference_ids_match_evidence_ids")
        else:
            status = "fail"
            failed_checks.append(
                {
                    "claim_id": claim["claim_id"],
                    "code": "reference_mismatch",
                    "detail": "mapped_reference_ids_not_subset_of_evidence_reference_ids",
                }
            )

        claim_audits.append(
            {
                "claim_id": claim["claim_id"],
                "status": status,
                "checks": checks,
            }
        )

    passed_claims = sum(1 for audit in claim_audits if audit["status"] == "pass")
    failed_claims = len(claim_audits) - passed_claims

    return {
        "audit_summary": {
            "total_claims": len(claim_audits),
            "passed_claims": passed_claims,
            "failed_claims": failed_claims,
        },
        "claim_audits": claim_audits,
        "failed_checks": failed_checks,
    }
