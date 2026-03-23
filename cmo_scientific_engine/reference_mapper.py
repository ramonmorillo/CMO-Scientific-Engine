"""Reference mapping for the CMO Scientific Engine."""

from __future__ import annotations

from typing import Any, Dict, List


Reference = Dict[str, Any]


class ReferenceMappingError(ValueError):
    """Raised when references cannot be mapped safely."""


REQUIRED_REFERENCE_KEYS = ("reference_id", "citation", "finding_ids")


def _validate_reference_library(reference_library: List[Reference]) -> None:
    for reference in reference_library:
        missing = [key for key in REQUIRED_REFERENCE_KEYS if key not in reference]
        if missing:
            raise ReferenceMappingError(
                f"reference {reference.get('reference_id', '<missing>')} missing keys: {missing}"
            )


def map_references(claims_json: Dict[str, Any], reference_library: List[Reference]) -> Dict[str, Any]:
    """Map claims to supporting references using evidence identifiers."""
    _validate_reference_library(reference_library)

    references_by_id = {reference["reference_id"]: reference for reference in reference_library}
    claim_reference_map = []
    unmapped_claims = []

    for claim in claims_json.get("claims", []):
        reference_ids = []
        citations = []
        claim_finding_ids = set(claim["finding_ids"])
        for reference_id in claim["evidence_reference_ids"]:
            reference = references_by_id.get(reference_id)
            if reference is None:
                continue
            if not claim_finding_ids.intersection(reference["finding_ids"]):
                continue
            reference_ids.append(reference_id)
            citations.append(reference["citation"])

        if not reference_ids:
            unmapped_claims.append(claim["claim_id"])

        claim_reference_map.append(
            {
                "claim_id": claim["claim_id"],
                "reference_ids": reference_ids,
                "citations": citations,
            }
        )

    return {
        "claim_reference_map": claim_reference_map,
        "unmapped_claims": unmapped_claims,
    }
