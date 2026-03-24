# PubMed Verifier

`cmo_scientific_engine.pubmed_verifier` verifies citations against PubMed and searches candidates for claims.

## APIs

Uses official NCBI E-Utilities only:
- ESearch: `esearch.fcgi`
- ESummary: `esummary.fcgi`

## Environment

Optional API key:

```bash
export NCBI_API_KEY="..."
```

## Safeguards

- Request timeout (default 10s)
- Retry with backoff (default 2 retries)
- Rate-limit friendly throttle (default max 3 requests/second)

## Citation verification mode

```bash
python -m cmo_scientific_engine.pubmed_verifier --citation "PMID: 31452104"
```

Output schema:

```json
{
  "query": "...",
  "match_status": "verified|ambiguous|not_found",
  "pmid": "string|null",
  "title": "string|null",
  "journal": "string|null",
  "year": "string|null",
  "doi": "string|null"
}
```

## Claim search mode

```bash
python -m cmo_scientific_engine.pubmed_verifier --claim "sleep extension improves cognition" --study-type "systematic review"
```

Output schema:

```json
{
  "query": "...",
  "candidates": [
    {
      "pmid": "string",
      "title": "string",
      "journal": "string",
      "year": "string",
      "doi": "string|null"
    }
  ]
}
```

## Pipeline integration

When pipeline input sets `enable_pubmed_verifier: true`, the pipeline attempts PubMed verification for references currently marked `FAILED`.

- If PubMed finds a match, status is upgraded to `VERIFIED` and metadata is enriched (`pmid`, `doi`, `title`, `journal`, `year`).
- If PubMed does not find a match, status remains `FAILED`.
