"""Reference mapping for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


Reference = Dict[str, Any]
ALLOWED_EVIDENCE_MATCH = ("HIGH", "MODERATE", "LOW")


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


def _infer_reference_evidence_type(citation: str) -> str:
    normalized = citation.lower()
    if "meta-analysis" in normalized:
        return "meta-analysis"
    if "systematic review" in normalized:
        return "systematic review"
    if any(token in normalized for token in ("guideline", "consensus", "recommendation", "statement")):
        return "guideline"
    if any(token in normalized for token in ("randomized", "trial", "placebo", "controlled")):
        return "RCT"
    if " after " in f" {normalized} " and any(
        token in normalized for token in ("extension", "intervention", "protocol", "treatment")
    ):
        return "RCT"
    if any(
        token in normalized
        for token in (
            "cohort",
            "registry",
            "cross-sectional",
            "case-control",
            "observational",
            "patterns",
        )
    ):
        return "observational"
    if any(token in normalized for token in ("framework", "mechanism", "conceptual", "hypothesis")):
        return "conceptual"
    return "observational"


def _citation_is_structured(citation: str) -> bool:
    return bool(re.search(r"\b(19|20)\d{2}\b", citation)) and ";" in citation and "." in citation


def _evidence_alignment(required: str, observed: str) -> str:
    if required == observed:
        return "HIGH"
    compatible_pairs: Set[tuple[str, str]] = {
        ("meta-analysis", "systematic review"),
        ("systematic review", "meta-analysis"),
        ("RCT", "meta-analysis"),
        ("RCT", "systematic review"),
        ("observational", "systematic review"),
    }
    if (required, observed) in compatible_pairs:
        return "MODERATE"
    return "LOW"


def map_references(claims_json: Dict[str, Any], reference_library: List[Reference]) -> Dict[str, Any]:
    """Map claims to supporting references using evidence identifiers."""
    _validate_reference_library(reference_library)

    references_by_id = {reference["reference_id"]: reference for reference in reference_library}
    claim_reference_map = []
    unmapped_claims = []

    for claim in claims_json.get("claims", []):
        reference_ids = []
        citations = []
        evidence_match = []
        mismatch_flags = []
        claim_finding_ids = set(claim["finding_ids"])
        evidence_needed = claim.get("evidence_needed", "observational")
        for reference_id in claim["evidence_reference_ids"]:
            reference = references_by_id.get(reference_id)
            if reference is None:
                continue
            if not claim_finding_ids.intersection(reference["finding_ids"]):
                continue
            citation = reference["citation"]
            observed_evidence = _infer_reference_evidence_type(citation)
            match = _evidence_alignment(evidence_needed, observed_evidence)
            if not _citation_is_structured(citation):
                match = "LOW"
            reference_ids.append(reference_id)
            citations.append(citation)
            evidence_match.append(match)
            if match == "LOW":
                mismatch_flags.append("evidence_needed_mismatch")
            elif match == "MODERATE":
                mismatch_flags.append("partial_evidence_alignment")
            else:
                mismatch_flags.append("none")

        if not reference_ids:
            unmapped_claims.append(claim["claim_id"])

        claim_reference_map.append(
            {
                "claim_id": claim["claim_id"],
                "reference_ids": reference_ids,
                "citations": citations,
                "evidence_match": evidence_match,
                "mismatch_flags": mismatch_flags,
            }
        )

    return {
        "claim_reference_map": claim_reference_map,
        "unmapped_claims": unmapped_claims,
        "allowed_evidence_match": list(ALLOWED_EVIDENCE_MATCH),
    }
