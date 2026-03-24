---
name: auditor
description: Audit claim-to-reference consistency for the final validation step of the CMO Scientific Engine pipeline. Use when Codex needs to verify reference coverage, identifier integrity, and evidence traceability before merging outputs.
---

# auditor

## Instructions
- Read claims JSON and reference mapping JSON.
- Validate claim IDs, finding IDs, mapped reference IDs, and evidence-support conditions.
- Review each claim as a scientific reviewer, not only a structural validator.
- Fail any claim missing mapped references.
- Fail any mapping that points to an unknown claim.
- Enforce conservative scientific judgment when verification or methods are incomplete.
- Emit JSON only.
- Keep failure reasons short and enumerable.
- Distinguish `severity` as `fail` or `warning`.

## Required Input Keys
```json
{
  "claims": [
    {
      "claim_id": "string",
      "finding_ids": ["string"],
      "evidence_needed": "string",
      "text": "string"
    }
  ],
  "claim_reference_map": [
    {
      "claim_id": "string",
      "reference_ids": ["string"],
      "reference_verification_status": ["VERIFIED|UNVERIFIED|FAILED"],
      "evidence_match": ["HIGH|MODERATE|LOW"],
      "mismatch_flags": ["string"]
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
    "failed_claims": 0,
    "high_quality_evidence_pct": 0.0,
    "weakly_supported_pct": 0.0,
    "scientific_reliability_score": 0.0
  },
  "claim_audits": [
    {
      "claim_id": "string",
      "status": "pass|fail",
      "checks": ["string"],
      "evidence_level_ok": "YES|NO",
      "direct_support": "YES|NO",
      "risk_of_bias": "LOW|MODERATE|HIGH",
      "overclaiming": "YES|NO",
      "support_confidence": "HIGH|MODERATE|LOW|UNCERTAIN",
      "reference_verification_status": ["VERIFIED|UNVERIFIED|FAILED"]
    }
  ],
  "failed_checks": [
    {
      "claim_id": "string",
      "code": "string",
      "detail": "string",
      "severity": "fail|warning"
    }
  ]
}
```

## JSON Rules
- `checks` must contain only machine-readable tokens.
- `failed_checks` must be empty only when all claims pass with no warnings.
- `audit_summary` counts must match `claim_audits` exactly.
- Fail the pipeline if references are missing or if weakly supported claims exceed 30%.
- Emit a warning, not a fail, for evidence mismatches unless another fail condition applies.
- Do not expect claim-level reference IDs; audit mapped evidence only.
- If `reference_verification_status != VERIFIED`, corresponding `evidence_match` cannot be `HIGH`.
- `risk_of_bias` cannot be `LOW` when comparator, uncertainty/CI, study design, or sample size clarity is incomplete.
- If causal language is used without confirmed randomized design, set `overclaiming: YES` and add `causal_overclaim`.
- Add warning codes when applicable: `unverified_reference`, `causal_overclaim`, `incomplete_methods`.
