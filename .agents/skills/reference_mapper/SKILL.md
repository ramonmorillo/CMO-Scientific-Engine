---
name: reference_mapper
description: Map scientific claims to supporting references using finding overlap. Use when Codex needs the second step of the CMO Scientific Engine pipeline: attaching deterministic reference objects to claims without adding unsupported citations.
---

# reference_mapper

## Instructions
- Read claims JSON from `manuscript_generator`.
- Read `reference_library` from the source input.
- Map references independently from source findings; do not rely on claim-level reference IDs.
- Attach a reference only when its `finding_ids` overlap the claim's `finding_ids`.
- Preserve claim order.
- Emit JSON only.
- Never fabricate a citation.
- Infer reference evidence type from the supplied citation only.
- Score each mapped reference with `evidence_match`: `HIGH`, `MODERATE`, or `LOW`.
- If evidence type mismatches claim needs, keep the reference but flag the mismatch.

## Required Input Keys
```json
{
  "claims": [
    {
      "claim_id": "string",
      "finding_ids": ["string"],
      "text": "string",
      "priority": "primary|secondary",
      "evidence_needed": "string"
    }
  ],
  "reference_library": [
    {
      "reference_id": "string",
      "citation": "string",
      "finding_ids": ["string"]
    }
  ]
}
```

## Output Schema
```json
{
  "claim_reference_map": [
    {
      "claim_id": "string",
      "reference_ids": ["string"],
      "citations": ["string"],
      "evidence_match": ["HIGH|MODERATE|LOW"],
      "mismatch_flags": ["none|partial_evidence_alignment|evidence_needed_mismatch"]
    }
  ],
  "unmapped_claims": ["string"],
  "allowed_evidence_match": ["HIGH", "MODERATE", "LOW"]
}
```

## JSON Rules
- `claim_reference_map` must contain every claim exactly once.
- `reference_ids`, `citations`, `evidence_match`, and `mismatch_flags` must be aligned by index.
- `unmapped_claims` must list claim IDs with zero mapped references.
- Mapping order must be deterministic; sort references by `reference_id` when multiple overlap.
