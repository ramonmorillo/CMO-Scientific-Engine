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
