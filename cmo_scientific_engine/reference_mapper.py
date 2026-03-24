"""Reference mapping for the CMO Scientific Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


Reference = Dict[str, Any]
ALLOWED_EVIDENCE_MATCH = ("HIGH", "MODERATE", "LOW")
ALLOWED_VERIFICATION_STATUS = ("VERIFIED", "UNVERIFIED", "FAILED")
REQUIRED_REFERENCE_KEYS = ("reference_id", "citation", "finding_ids")


class ReferenceMappingError(ValueError):
    """Raised when references cannot be mapped safely."""


def _validate_reference_library(reference_library: List[Reference]) -> None:
    seen_reference_ids = set()
    for reference in reference_library:
        missing = [key for key in REQUIRED_REFERENCE_KEYS if key not in reference]
        if missing:
            raise ReferenceMappingError(
                f"reference {reference.get('reference_id', '<missing>')} missing keys: {missing}"
            )
        if reference["reference_id"] in seen_reference_ids:
            raise ReferenceMappingError(f"duplicate reference_id: {reference['reference_id']}")
        seen_reference_ids.add(reference["reference_id"])
        if not reference["finding_ids"]:
            raise ReferenceMappingError(
                f"reference {reference['reference_id']} missing finding_ids"
            )


def _infer_reference_evidence_type(citation: str) -> str:
    normalized = citation.lower()
    if "meta-analysis" in normalized:
        return "meta-analysis"
    if "systematic review" in normalized or "review of" in normalized:
        return "systematic review"
    if any(token in normalized for token in ("guideline", "consensus", "recommendation", "statement")):
        return "guideline"
    if any(token in normalized for token in ("randomized", "trial", "placebo", "controlled")):
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
            "adherence",
        )
    ):
        return "observational"
    if any(token in normalized for token in ("framework", "mechanism", "conceptual", "hypothesis")):
        return "conceptual"
    return "observational"


def _citation_is_structured(citation: str) -> bool:
    return bool(re.search(r"\b(19|20)\d{2}\b", citation)) and ";" in citation and "." in citation


def _normalized_reference_title(reference: Reference) -> str:
    title = str(reference.get("title", "")).strip().lower()
    if title:
        return re.sub(r"\s+", " ", title)

    citation = str(reference.get("citation", "")).strip()
    parts = [segment.strip() for segment in citation.split(".") if segment.strip()]
    if len(parts) >= 2:
        return re.sub(r"\s+", " ", parts[1].lower())
    return ""


def _reference_verification_status(reference: Reference) -> str:
    citation = str(reference.get("citation", "")).strip()
    if not _citation_is_structured(citation):
        return "FAILED"

    traceable_identifier = any(str(reference.get(key, "")).strip() for key in ("doi", "pmid", "url"))
    if not traceable_identifier:
        return "FAILED"

    trusted_metadata = all(
        str(reference.get(key, "")).strip()
        for key in ("title", "journal", "year")
    )
    if traceable_identifier or trusted_metadata:
        metadata_title = _normalized_reference_title(reference)
        citation_title = _normalized_reference_title({"citation": citation})
        if metadata_title and citation_title and metadata_title != citation_title:
            return "FAILED"
        return "VERIFIED"
    return "UNVERIFIED"


def _evidence_alignment(required: str, observed: str) -> str:
    if required == observed:
        return "HIGH"
    compatible_pairs: Set[tuple[str, str]] = {
        ("meta-analysis", "systematic review"),
        ("systematic review", "meta-analysis"),
        ("RCT", "meta-analysis"),
        ("RCT", "systematic review"),
        ("observational", "systematic review"),
        ("observational", "meta-analysis"),
    }
    if (required, observed) in compatible_pairs:
        return "MODERATE"
    return "LOW"


def _apply_verification_constraints(match: str, verification_status: str) -> str:
    if verification_status == "VERIFIED":
        return match
    if verification_status == "FAILED":
        return "LOW"
    if match == "HIGH":
        return "MODERATE"
    return match


def map_references(claims_json: Dict[str, Any], reference_library: List[Reference]) -> Dict[str, Any]:
    """Map claims to supporting references from finding overlap."""
    _validate_reference_library(reference_library)

    claim_reference_map = []
    unmapped_claims = []

    for claim in claims_json.get("claims", []):
        reference_ids = []
        citations = []
        evidence_match = []
        mismatch_flags = []
        reference_verification_status = []
        claim_finding_ids = set(claim["finding_ids"])
        evidence_needed = claim.get("evidence_needed", "observational")
        candidate_references = sorted(
            (
                reference
                for reference in reference_library
                if claim_finding_ids.intersection(reference["finding_ids"])
            ),
            key=lambda item: item["reference_id"],
        )

        for reference in candidate_references:
            citation = reference["citation"]
            observed_evidence = _infer_reference_evidence_type(citation)
            match = _evidence_alignment(evidence_needed, observed_evidence)
            verification_status = _reference_verification_status(reference)
            match = _apply_verification_constraints(match, verification_status)
            reference_ids.append(reference["reference_id"])
            citations.append(citation)
            evidence_match.append(match)
            reference_verification_status.append(verification_status)
            if verification_status == "FAILED":
                mismatch_flags.append("reference_verification_failed")
            elif verification_status == "UNVERIFIED":
                mismatch_flags.append("reference_unverified")
            elif match == "LOW":
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
                "reference_verification_status": reference_verification_status,
                "mismatch_flags": mismatch_flags,
            }
        )

    return {
        "claim_reference_map": claim_reference_map,
        "unmapped_claims": unmapped_claims,
        "allowed_evidence_match": list(ALLOWED_EVIDENCE_MATCH),
        "allowed_reference_verification_status": list(ALLOWED_VERIFICATION_STATUS),
    }
