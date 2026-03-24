"""PubMed verification utilities for CMO Scientific Engine."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRIES = 2
DEFAULT_MAX_REQUESTS_PER_SECOND = 3.0
PMID_PATTERN = re.compile(r"\bPMID\s*:?\s*(\d{4,9})\b", re.IGNORECASE)
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


@dataclass
class PubMedVerifierClient:
    """Small PubMed E-Utilities client with rate limiting and retries."""

    api_key: Optional[str] = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES
    max_requests_per_second: float = DEFAULT_MAX_REQUESTS_PER_SECOND

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        if self.max_requests_per_second <= 0:
            raise ValueError("max_requests_per_second must be positive")

    def _throttle(self) -> None:
        min_interval = 1.0 / self.max_requests_per_second
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_at = time.monotonic()

    def _request_json(self, endpoint: str, params: Dict[str, str]) -> Dict[str, Any]:
        query = dict(params)
        query["retmode"] = "json"
        if self.api_key:
            query["api_key"] = self.api_key

        url = f"{EUTILS_BASE}/{endpoint}?{urllib.parse.urlencode(query)}"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                self._throttle()
                with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = response.read().decode("utf-8")
                    return json.loads(payload)
            except Exception as exc:  # stdlib network errors vary by type
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(min(0.5 * (2**attempt), 2.0))

        raise RuntimeError(f"PubMed API request failed for {endpoint}: {last_error}")

    def esearch(self, term: str, retmax: int = 5) -> List[str]:
        response = self._request_json(
            "esearch.fcgi",
            {"db": "pubmed", "term": term, "retmax": str(retmax), "sort": "relevance"},
        )
        return response.get("esearchresult", {}).get("idlist", [])

    def esummary(self, pmids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not pmids:
            return {}
        response = self._request_json(
            "esummary.fcgi",
            {"db": "pubmed", "id": ",".join(pmids)},
        )
        result = response.get("result", {})
        return {pmid: result.get(pmid, {}) for pmid in pmids}


def _extract_year(pubdate: str) -> Optional[str]:
    if not pubdate:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", pubdate)
    return match.group(0) if match else None


def _extract_doi(article_ids: Any) -> Optional[str]:
    if not isinstance(article_ids, list):
        return None
    for item in article_ids:
        if str(item.get("idtype", "")).lower() == "doi":
            value = str(item.get("value", "")).strip()
            if value:
                return value
    return None


def _summary_to_candidate(pmid: str, summary: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {
        "pmid": pmid,
        "title": summary.get("title") or None,
        "journal": summary.get("fulljournalname") or summary.get("source") or None,
        "year": _extract_year(summary.get("pubdate", "")),
        "doi": _extract_doi(summary.get("articleids", [])),
    }


def _citation_query(citation: str) -> str:
    normalized = citation.strip()
    pmid_match = PMID_PATTERN.search(normalized)
    if pmid_match:
        return f"{pmid_match.group(1)}[PMID]"
    doi_match = DOI_PATTERN.search(normalized.upper())
    if doi_match:
        return f"{doi_match.group(0)}[DOI]"
    return normalized


def verify_citation(citation: str, client: Optional[PubMedVerifierClient] = None) -> Dict[str, Optional[str]]:
    """Verify a free-text citation against PubMed using ESearch + ESummary."""
    pubmed_client = client or PubMedVerifierClient(api_key=os.getenv("NCBI_API_KEY"))
    query = _citation_query(citation)
    pmids = pubmed_client.esearch(query, retmax=3)

    if not pmids:
        return {
            "query": query,
            "match_status": "not_found",
            "pmid": None,
            "title": None,
            "journal": None,
            "year": None,
            "doi": None,
        }

    summaries = pubmed_client.esummary(pmids)
    best = _summary_to_candidate(pmids[0], summaries.get(pmids[0], {}))
    match_status = "verified" if len(pmids) == 1 else "ambiguous"

    return {
        "query": query,
        "match_status": match_status,
        "pmid": best["pmid"],
        "title": best["title"],
        "journal": best["journal"],
        "year": best["year"],
        "doi": best["doi"],
    }


def search_claim(
    claim_text: str,
    study_type: Optional[str] = None,
    client: Optional[PubMedVerifierClient] = None,
    max_candidates: int = 5,
) -> Dict[str, Any]:
    """Search candidate PubMed papers for a claim query."""
    pubmed_client = client or PubMedVerifierClient(api_key=os.getenv("NCBI_API_KEY"))
    query = claim_text.strip()
    if study_type:
        query = f"{query} AND {study_type.strip()}"

    pmids = pubmed_client.esearch(query, retmax=max_candidates)
    summaries = pubmed_client.esummary(pmids)
    candidates = [_summary_to_candidate(pmid, summaries.get(pmid, {})) for pmid in pmids]

    return {"query": query, "candidates": candidates}


def enrich_failed_references(
    claim_reference_map: List[Dict[str, Any]],
    reference_library: List[Dict[str, Any]],
    client: Optional[PubMedVerifierClient] = None,
) -> List[Dict[str, Any]]:
    """Upgrade FAILED verification statuses to VERIFIED when PubMed confirms them."""
    pubmed_client = client or PubMedVerifierClient(api_key=os.getenv("NCBI_API_KEY"))
    ref_by_id = {item.get("reference_id"): item for item in reference_library}

    for mapping in claim_reference_map:
        reference_ids = mapping.get("reference_ids", [])
        statuses = list(mapping.get("reference_verification_status", []))
        for index, reference_id in enumerate(reference_ids):
            if index >= len(statuses) or statuses[index] != "FAILED":
                continue
            reference = ref_by_id.get(reference_id)
            if not reference:
                continue
            result = verify_citation(reference.get("citation", ""), client=pubmed_client)
            if result["match_status"] != "not_found":
                statuses[index] = "VERIFIED"
                reference["pmid"] = result["pmid"]
                reference["doi"] = result["doi"]
                reference["title"] = result["title"]
                reference["journal"] = result["journal"]
                reference["year"] = result["year"]
        mapping["reference_verification_status"] = statuses
    return claim_reference_map


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PubMed citation verifier")
    parser.add_argument("--citation", help="Free-text citation to verify")
    parser.add_argument("--claim", help="Claim text for candidate article search")
    parser.add_argument("--study-type", help="Optional study type filter", default=None)
    parser.add_argument("--max-candidates", type=int, default=5)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if bool(args.citation) == bool(args.claim):
        parser.error("Provide exactly one of --citation or --claim")

    if args.citation:
        print(json.dumps(verify_citation(args.citation), indent=2))
        return 0

    print(
        json.dumps(
            search_claim(
                args.claim,
                study_type=args.study_type,
                max_candidates=max(1, args.max_candidates),
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
