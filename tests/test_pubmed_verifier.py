"""Tests for PubMed verifier module."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from cmo_scientific_engine.pubmed_verifier import (
    PubMedVerifierClient,
    enrich_failed_references,
    search_claim,
    verify_citation,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class PubMedVerifierTests(unittest.TestCase):
    def test_verify_citation_verified(self) -> None:
        esearch_payload = {"esearchresult": {"idlist": ["12345"]}}
        esummary_payload = {
            "result": {
                "12345": {
                    "title": "Example article",
                    "fulljournalname": "Example Journal",
                    "pubdate": "2024 Jan",
                    "articleids": [{"idtype": "doi", "value": "10.1000/example"}],
                }
            }
        }

        with patch("urllib.request.urlopen", side_effect=[_FakeResponse(esearch_payload), _FakeResponse(esummary_payload)]):
            result = verify_citation("PMID: 12345", client=PubMedVerifierClient(max_requests_per_second=1000))

        self.assertEqual(result["match_status"], "verified")
        self.assertEqual(result["pmid"], "12345")
        self.assertEqual(result["doi"], "10.1000/example")
        self.assertEqual(result["year"], "2024")

    def test_verify_citation_not_found(self) -> None:
        esearch_payload = {"esearchresult": {"idlist": []}}
        with patch("urllib.request.urlopen", return_value=_FakeResponse(esearch_payload)):
            result = verify_citation("unknown citation", client=PubMedVerifierClient(max_requests_per_second=1000))

        self.assertEqual(result["match_status"], "not_found")
        self.assertIsNone(result["pmid"])

    def test_search_claim_returns_candidates(self) -> None:
        esearch_payload = {"esearchresult": {"idlist": ["111", "222"]}}
        esummary_payload = {
            "result": {
                "111": {
                    "title": "Trial one",
                    "fulljournalname": "Journal A",
                    "pubdate": "2021 May",
                    "articleids": [{"idtype": "doi", "value": "10.1000/a"}],
                },
                "222": {
                    "title": "Trial two",
                    "source": "Journal B",
                    "pubdate": "2020",
                    "articleids": [],
                },
            }
        }

        with patch("urllib.request.urlopen", side_effect=[_FakeResponse(esearch_payload), _FakeResponse(esummary_payload)]):
            result = search_claim(
                "sleep extension cognition",
                study_type="systematic review",
                client=PubMedVerifierClient(max_requests_per_second=1000),
            )

        self.assertIn("systematic review", result["query"])
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["candidates"][1]["doi"], None)

    def test_enrich_failed_references_upgrades_failed(self) -> None:
        claim_reference_map = [
            {
                "claim_id": "CLM-001",
                "reference_ids": ["REF-001"],
                "reference_verification_status": ["FAILED"],
            }
        ]
        reference_library = [{"reference_id": "REF-001", "citation": "PMID: 12345"}]

        with patch(
            "cmo_scientific_engine.pubmed_verifier.verify_citation",
            return_value={
                "query": "12345[PMID]",
                "match_status": "verified",
                "pmid": "12345",
                "title": "Example article",
                "journal": "Example Journal",
                "year": "2024",
                "doi": "10.1000/example",
            },
        ):
            updated = enrich_failed_references(claim_reference_map, reference_library, client=PubMedVerifierClient(max_requests_per_second=1000))

        self.assertEqual(updated[0]["reference_verification_status"], ["VERIFIED"])
        self.assertEqual(reference_library[0]["pmid"], "12345")


if __name__ == "__main__":
    unittest.main()
