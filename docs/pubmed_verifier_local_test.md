# PubMed Verifier Local Test Guide

Use this only on a machine with outbound access to `https://eutils.ncbi.nlm.nih.gov`.

## 1) Setup

1. Open the repo root.
2. (Optional) set NCBI API key for higher rate limits:

```bash
export NCBI_API_KEY="your_key_here"
```

## 2) Run quick real/fake citation checks

### Real citation test (expected `verified`)

```bash
python -m cmo_scientific_engine.pubmed_verifier --citation "PMID: 31978945"
```

Expected:
- `match_status: "verified"`
- `pmid: "31978945"`
- title/journal/year populated

### Fake citation test (expected `not_found`)

```bash
python -m cmo_scientific_engine.pubmed_verifier --citation "PMID: 999999999"
```

Expected:
- `match_status: "not_found"`
- `pmid: null`

## 3) Additional real retrieval case (known PubMed article)

Use DOI for the NEJM COVID-19 paper (`10.1056/NEJMoa2001017`), which is indexed as PMID `31978945`.

```bash
python -m cmo_scientific_engine.pubmed_verifier --citation "10.1056/NEJMoa2001017"
```

Expected:
- `query: "10.1056/NEJMOA2001017[DOI]"`
- `match_status: "verified"`
- `pmid: "31978945"`

## 4) Expected JSON status patterns

### `verified`
Single clear PubMed match.

```json
{
  "match_status": "verified",
  "pmid": "<pmid>",
  "title": "<non-null>",
  "journal": "<non-null>",
  "year": "<yyyy>",
  "doi": "<doi-or-null>"
}
```

### `not_found`
No PubMed IDs returned by ESearch.

```json
{
  "match_status": "not_found",
  "pmid": null,
  "title": null,
  "journal": null,
  "year": null,
  "doi": null
}
```

### `ambiguous`
Multiple PubMed IDs returned; first candidate is emitted.

```json
{
  "match_status": "ambiguous",
  "pmid": "<first_candidate_pmid>",
  "title": "<candidate_title>",
  "journal": "<candidate_journal>",
  "year": "<candidate_year>",
  "doi": "<candidate_doi_or_null>"
}
```

Quick way to trigger locally:

```bash
python -m cmo_scientific_engine.pubmed_verifier --citation "cancer"
```

### `api_unavailable`
Network/proxy/DNS blocked or PubMed unreachable after retries.

```json
{
  "match_status": "api_unavailable",
  "pmid": null,
  "title": null,
  "journal": null,
  "year": null,
  "doi": null,
  "verification_status": "deferred",
  "error_class": "network_or_proxy"
}
```

## 5) Optional sanity command in restricted environments

If your environment is blocked, this command should return `api_unavailable` rather than crashing:

```bash
python -m cmo_scientific_engine.pubmed_verifier --citation "PMID: 31978945"
```
