# article_strategy_engine

`article_strategy_engine` routes free-text scientific ideas to the most suitable article type.

Supported types:
- `original_article`
- `systematic_review`
- `scoping_review`
- `narrative_review`
- `conceptual_article`
- `editorial_or_commentary`

## Input

English or Spanish free text:
- scientific idea
- short summary
- abstract
- project description

## Output schema

```json
{
  "recommended_article_type": "string",
  "confidence": "high|moderate|low",
  "rationale": ["string"],
  "alternative_types": ["string"],
  "required_elements": ["string"],
  "missing_elements": ["string"]
}
```

## Routing rules

- Conservative recommendations; no invented study details.
- `original_article` requires explicit empirical signals (design + population/data source + outcomes).
- `systematic_review` requires formal synthesis cues (search strategy, eligibility/risk-of-bias, comparative synthesis intent).
- `scoping_review` is preferred for broad evidence mapping and gap-identification aims.
- `conceptual_article` is preferred for definitional/theoretical/methodological framing.
- `editorial_or_commentary` is selected when perspective/position language dominates without formal methods.
- Defaults to `narrative_review` when intent is review-like but protocol rigor is underspecified.

## CLI

```bash
python -m cmo_scientific_engine.article_strategy_engine --text "Objective: evaluate intervention effects in 120 participants in a randomized trial."
```
