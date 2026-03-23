# CMO-Scientific-Engine

JSON-only scientific drafting pipeline with claim generation, reference mapping, auditing, and merged output.

## Input schema
- `findings[].raw_result`: concise, testable source result text used to generate claim text.
- `findings[].uncertainty`: source certainty qualifier used during evidence inference.
- `findings[].priority`: `primary` or `secondary`.
- `findings[]` must not contain deprecated `claim_text` or `evidence_reference_ids` fields.
- `reference_mapper` assigns references independently from `reference_library[].finding_ids` overlap.
