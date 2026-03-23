---
name: manuscript_generator
description: Generate structured scientific manuscript claims JSON from study metadata and findings. Use when Codex needs to turn source findings into compact, evidence-linked claim objects for the first step of the CMO Scientific Engine pipeline.
---

# manuscript_generator

## Instructions
- Read structured study input only.
- Generate one claim per finding unless two findings are exact duplicates.
- Preserve source identifiers exactly.
- Keep claims concise, factual, and publication-ready.
- Do not invent statistics, cohorts, p-values, outcomes, or references.
- Emit JSON only.

## Required Input Keys
```json
{
  "study": {
    "study_id": "string",
    "title": "string",
    "domain": "string",
    "objective": "string"
  },
  "findings": [
    {
      "finding_id": "string",
      "claim_text": "string",
      "evidence_reference_ids": ["string"],
      "priority": "primary|secondary"
    }
  ],
  "reference_library": []
}
```

## Output Schema
```json
{
  "study": {
    "study_id": "string",
    "title": "string",
    "domain": "string",
    "objective": "string"
  },
  "claims": [
    {
      "claim_id": "CLM-001",
      "finding_ids": ["string"],
      "text": "string",
      "priority": "primary|secondary",
      "evidence_reference_ids": ["string"]
    }
  ],
  "generation_notes": {
    "claim_count": 0,
    "deduplicated_findings": []
  }
}
```

## JSON Rules
- `claim_id` must be sequential in the emitted order.
- `finding_ids` must be non-empty.
- `evidence_reference_ids` must mirror the source finding.
- `generation_notes` must stay machine-readable; do not add prose.
