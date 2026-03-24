"""Pipeline orchestration for the CMO Scientific Engine."""

from __future__ import annotations

from typing import Any, Dict

from .auditor import audit_claims
from .manuscript_generator import generate_claims
from .reference_mapper import map_references
from .pubmed_verifier import enrich_failed_references


PipelineResult = Dict[str, Any]


def _prepare_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "free_text" not in payload:
        return payload

    from .free_text_ingest import ingest_free_text

    structured = ingest_free_text(str(payload.get("free_text", "")))
    prepared = {
        "study": structured["study"],
        "findings": [
            {
                "finding_id": finding["finding_id"],
                "raw_result": finding["raw_result"],
                "priority": finding["priority"] if finding["priority"] in {"primary", "secondary"} else "secondary",
                "uncertainty": finding["uncertainty"],
            }
            for finding in structured["findings"]
        ],
        "reference_library": payload.get("reference_library", []),
        "enable_pubmed_verifier": payload.get("enable_pubmed_verifier", False),
    }
    return prepared


def run_pipeline(payload: Dict[str, Any]) -> PipelineResult:
    """Run the full four-step scientific pipeline."""
    prepared_payload = _prepare_payload(payload)
    claims_json = generate_claims(prepared_payload)
    reference_library = prepared_payload.get("reference_library", [])
    mapping_json = map_references(claims_json, reference_library)
    if prepared_payload.get("enable_pubmed_verifier", False):
        mapping_json["claim_reference_map"] = enrich_failed_references(
            mapping_json["claim_reference_map"],
            reference_library,
        )
    audit_json = audit_claims(claims_json, mapping_json)
    rewritten_by_id = {item["claim_id"]: item["text"] for item in audit_json.get("rewritten_claims", [])}
    audited_claims = []
    for claim in claims_json["claims"]:
        updated_claim = dict(claim)
        if claim["claim_id"] in rewritten_by_id:
            updated_claim["text"] = rewritten_by_id[claim["claim_id"]]
        audited_claims.append(updated_claim)
    failing_checks = [item for item in audit_json["failed_checks"] if item["severity"] == "fail"]

    return {
        "study": claims_json["study"],
        "claims": audited_claims,
        "claim_reference_map": mapping_json["claim_reference_map"],
        "audit_summary": audit_json["audit_summary"],
        "claim_audits": audit_json["claim_audits"],
        "failed_checks": audit_json["failed_checks"],
        "pipeline_status": "pass" if not failing_checks else "fail",
    }
