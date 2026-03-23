# CMO-Scientific-Engine

JSON-only scientific drafting pipeline with claim generation, reference mapping, auditing, and merged output.

## Input schema
- `findings[].raw_result`: concise, testable study result text.
- `findings[].uncertainty`: source certainty qualifier used during evidence inference.
- `findings[].priority`: `primary` or `secondary`.
- `reference_mapper` assigns references independently from `reference_library[].finding_ids` overlap.
