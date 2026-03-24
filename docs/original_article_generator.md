# original_article_generator

`original_article_generator` creates a structured original-article draft from free text, `free_text_ingest` output, and `article_strategy_engine` guidance.

## Inputs

- `text` (required): free-text scientific study description in Spanish or English.
- `free_text_ingest_output` (optional): structured JSON from `free_text_ingest`.
- `article_strategy_output` (optional): recommendation JSON from `article_strategy_engine`.

## Output schema

```json
{
  "article_type": "original_article",
  "title": "string",
  "sections": {
    "introduction": "string",
    "methods": "string",
    "results": "string",
    "discussion": "string"
  },
  "claims": [
    {
      "claim_id": "string",
      "text": "string",
      "section": "introduction|methods|results|discussion",
      "evidence_needed": "string",
      "certainty": "high|moderate|low|uncertain"
    }
  ],
  "missing_elements": ["string"],
  "warnings": ["string"]
}
```

## Rules implemented

- Never invents missing information.
- Explicitly marks incomplete methods in section text and warnings.
- Uses cautious language for findings.
- Reports results from provided findings only.
- Keeps discussion split between demonstrated results and interpretation.
- Emits warning when strategy does not recommend `original_article`.
- Detects Spanish/English input and matches output language.

## CLI

```bash
python -m cmo_scientific_engine.original_article_generator --text "..."
```

Optional structured/strategy JSON:

```bash
python -m cmo_scientific_engine.original_article_generator \
  --text "..." \
  --structured-json '{"study": {...}, "findings": [...], "missing_fields": []}' \
  --strategy-json '{"recommended_article_type": "original_article"}'
```

## Integration notes

- If `free_text_ingest_output` is not provided, the module calls `ingest_free_text(text)`.
- Claims are emitted with stable `CLM-###` IDs and certainty labels to support later mapping/auditing.
