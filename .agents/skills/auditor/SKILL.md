---
name: auditor
description: Audit claim-to-reference consistency for the final validation step of the CMO Scientific Engine pipeline. Use when Codex needs to verify reference coverage, identifier integrity, and evidence traceability before merging outputs.
---

# auditor

## Instructions
- Read claims JSON and reference mapping JSON.
- Validate claim IDs, finding IDs, and reference IDs.
- Fail any claim missing mapped references.
- Fail any mapping that points to an unknown claim.
- Emit JSON only.
- Keep failure reasons short and enumerable.

## Required Input Keys
```json
{
  "claims": [
    {
      "claim_id": "string",
      "finding_ids": ["string"],
      "evidence_reference_ids": ["string"]
    }
  ],
  "claim_reference_map": [
    {
      "claim_id": "string",
      "reference_ids": ["string"]
    }
  ]
}
```

## Output Schema
```json
{
  "audit_summary": {
    "total_claims": 0,
    "passed_claims": 0,
    "failed_claims": 0
  },
  "claim_audits": [
    {
      "claim_id": "string",
      "status": "pass|fail",
      "checks": ["has_findings", "has_references", "reference_ids_match_evidence_ids"]
    }
  ],
  "failed_checks": [
    {
      "claim_id": "string",
      "code": "string",
      "detail": "string"
    }
  ]
}
```

## JSON Rules
- `checks` must contain only machine-readable tokens.
- `failed_checks` must be empty when all claims pass.
- `audit_summary` counts must match `claim_audits` exactly.
