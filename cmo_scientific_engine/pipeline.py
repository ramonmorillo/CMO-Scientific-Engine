"""Pipeline orchestration for the CMO Scientific Engine."""

from __future__ import annotations

from typing import Any, Dict

from .auditor import audit_claims
from .manuscript_generator import generate_claims
from .reference_mapper import map_references


PipelineResult = Dict[str, Any]


def run_pipeline(payload: Dict[str, Any]) -> PipelineResult:
    """Run the full four-step scientific pipeline."""
    claims_json = generate_claims(payload)
    mapping_json = map_references(claims_json, payload.get("reference_library", []))
    audit_json = audit_claims(claims_json, mapping_json)

    return {
        "study": claims_json["study"],
        "claims": claims_json["claims"],
        "claim_reference_map": mapping_json["claim_reference_map"],
        "audit_summary": audit_json["audit_summary"],
        "claim_audits": audit_json["claim_audits"],
        "failed_checks": audit_json["failed_checks"],
        "pipeline_status": "pass" if not audit_json["failed_checks"] else "fail",
    }
