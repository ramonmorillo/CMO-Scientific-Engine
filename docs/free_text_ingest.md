# free_text_ingest

`free_text_ingest` transforms English or Spanish scientific prose into normalized JSON that the CMO pipeline can consume.

## Output schema

```json
{
  "study": {
    "study_id": "AUTO-001",
    "title": "string|null",
    "objective": "string|null",
    "design": "string|null",
    "population": "string|null",
    "duration": "string|null",
    "domain": "string|null"
  },
  "findings": [
    {
      "finding_id": "FND-001",
      "raw_result": "string",
      "priority": "primary|secondary|unknown",
      "uncertainty": "low|moderate|high|unknown"
    }
  ],
  "missing_fields": ["string"]
}
```

## Rules

- Missing study fields remain `null` and are listed in `missing_fields`.
- Findings are extracted conservatively from sentences with quantitative or directional signals.
- Study design is only assigned when explicitly stated in text.
- No references, evidence levels, or study details are fabricated.

## CLI

```bash
python -m cmo_scientific_engine.free_text_ingest --text "Objective: assess throughput. Randomized controlled trial in 80 workers. Throughput improved by 12 percent after 6 weeks."
```

## Pipeline integration

`run_pipeline` now accepts payloads with `free_text`:

```json
{
  "free_text": "...",
  "reference_library": []
}
```

Execution flow:
1. `free_text` → `ingest_free_text`
2. structured JSON → `manuscript_generator`
3. `reference_mapper`
4. `auditor`
