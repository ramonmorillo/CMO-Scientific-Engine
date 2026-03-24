"""Tests for the CMO Scientific Engine."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from cmo_scientific_engine import run_pipeline
from cmo_scientific_engine.auditor import audit_claims


class PipelineTests(unittest.TestCase):
    def _example_payload(self) -> dict:
        return json.loads(Path("examples/test_input.json").read_text())

    def _verified_payload(self) -> dict:
        payload = self._example_payload()
        payload["study"].update(
            {
                "design": "Randomized controlled trial",
                "design_details": "Parallel-group randomized controlled trial with allocation concealment.",
                "comparator": "Usual sleep schedule",
                "sample_size_justification": "Power calculation targeted 80 percent power for throughput change.",
                "confidence_interval": "95% confidence interval reported for primary and secondary outcomes.",
            }
        )
        payload["reference_library"][0].update(
            {
                "title": "Randomized trial of cognitive throughput after sleep extension",
                "journal": "J Sleep Metrics",
                "year": "2025",
                "doi": "10.1000/jsm.2025.201",
            }
        )
        payload["reference_library"][1].update(
            {
                "title": "Observational study of adherence patterns in behavioral sleep interventions",
                "journal": "Clin Protocols",
                "year": "2024",
                "doi": "10.1000/cp.2024.44",
            }
        )
        return payload

    def test_example_input_now_fails_conservatively(self) -> None:
        payload = self._example_payload()
        self.assertNotIn("claim_text", payload["findings"][0])
        self.assertNotIn("evidence_reference_ids", payload["findings"][0])

        result = run_pipeline(payload)

        self.assertEqual(result["pipeline_status"], "fail")
        self.assertEqual(result["audit_summary"]["total_claims"], 2)
        self.assertEqual(
            [claim["evidence_needed"] for claim in result["claims"]],
            ["RCT", "observational"],
        )
        self.assertIn("was associated with an increase", result["claims"][0]["text"])
        self.assertEqual(
            result["claim_reference_map"][0]["reference_verification_status"],
            ["FAILED"],
        )
        self.assertEqual(result["claim_reference_map"][0]["evidence_match"], ["LOW"])
        self.assertEqual(result["audit_summary"]["high_quality_evidence_pct"], 0.0)
        self.assertEqual(result["audit_summary"]["weakly_supported_pct"], 100.0)
        self.assertEqual(result["audit_summary"]["scientific_reliability_score"], 30.0)
        self.assertEqual(result["audit_summary"]["verification_integrity"], "MODERATE")
        self.assertEqual(
            [audit["support_confidence"] for audit in result["claim_audits"]],
            ["LOW", "LOW"],
        )
        self.assertEqual(
            [audit["risk_of_bias"] for audit in result["claim_audits"]],
            ["HIGH", "HIGH"],
        )
        self.assertEqual(
            [audit["direct_support"] for audit in result["claim_audits"]],
            ["NO", "NO"],
        )
        self.assertIn(
            {
                "claim_id": "GLOBAL",
                "code": "weak_support_threshold",
                "detail": "weakly_supported_claims_exceed_30_percent",
                "severity": "fail",
            },
            result["failed_checks"],
        )
        self.assertIn(
            {
                "claim_id": "CLM-001",
                "code": "incomplete_methods",
                "detail": "missing_design_details_comparator_sample_size_justification_confidence_interval",
                "severity": "fail",
            },
            result["failed_checks"],
        )

    def test_reference_mapper_tracks_verification_and_partial_alignment(self) -> None:
        payload = self._verified_payload()
        payload["reference_library"].append(
            {
                "reference_id": "REF-003",
                "citation": "Lopez T. Systematic review of sleep extension performance trials. Sleep Review. 2025;9(2):10-18.",
                "title": "Systematic review of sleep extension performance trials",
                "journal": "Sleep Review",
                "year": "2025",
                "doi": "10.1000/sr.2025.10",
                "finding_ids": ["FND-001"],
            }
        )
        result = run_pipeline(payload)
        mapped_items = {item["claim_id"]: item for item in result["claim_reference_map"]}

        self.assertEqual(mapped_items["CLM-001"]["reference_ids"], ["REF-001", "REF-003"])
        self.assertEqual(mapped_items["CLM-001"]["evidence_match"], ["HIGH", "MODERATE"])
        self.assertEqual(
            mapped_items["CLM-001"]["reference_verification_status"],
            ["VERIFIED", "VERIFIED"],
        )
        self.assertEqual(
            mapped_items["CLM-001"]["mismatch_flags"],
            ["none", "partial_evidence_alignment"],
        )
        self.assertEqual(mapped_items["CLM-002"]["reference_ids"], ["REF-002"])
        self.assertEqual(mapped_items["CLM-002"]["reference_verification_status"], ["VERIFIED"])
        self.assertIn(
            {
                "claim_id": "CLM-001",
                "code": "partial_evidence_alignment",
                "detail": "mapped_reference_partially_matches_needed_evidence",
                "severity": "warning",
            },
            result["failed_checks"],
        )
        self.assertEqual(result["pipeline_status"], "pass")

    def test_pipeline_passes_with_verified_references_and_complete_methods(self) -> None:
        payload = self._verified_payload()

        result = run_pipeline(payload)

        self.assertEqual(result["pipeline_status"], "pass")
        self.assertEqual(result["audit_summary"]["high_quality_evidence_pct"], 100.0)
        self.assertEqual(result["audit_summary"]["weakly_supported_pct"], 0.0)
        self.assertEqual(result["audit_summary"]["scientific_reliability_score"], 100.0)
        self.assertEqual(result["failed_checks"], [])
        self.assertEqual(
            [audit["support_confidence"] for audit in result["claim_audits"]],
            ["HIGH", "HIGH"],
        )
        self.assertEqual(
            [audit["risk_of_bias"] for audit in result["claim_audits"]],
            ["LOW", "MODERATE"],
        )

    def test_pipeline_fails_when_reference_verification_fails(self) -> None:
        payload = self._verified_payload()
        payload["reference_library"][0] = copy.deepcopy(payload["reference_library"][0])
        payload["reference_library"][0]["title"] = "Mismatched title that should fail verification"

        result = run_pipeline(payload)

        self.assertEqual(result["pipeline_status"], "fail")
        self.assertIn(
            {
                "claim_id": "CLM-001",
                "code": "reference_verification_failed",
                "detail": "reference_metadata_not_verifiable",
                "severity": "fail",
            },
            result["failed_checks"],
        )
        self.assertEqual(
            result["claim_reference_map"][0]["reference_verification_status"],
            ["FAILED"],
        )
        self.assertLessEqual(result["audit_summary"]["scientific_reliability_score"], 50.0)

    def test_pubmed_api_unavailable_is_treated_differently_than_not_found(self) -> None:
        payload = self._example_payload()
        payload["enable_pubmed_verifier"] = True

        with patch(
            "cmo_scientific_engine.pubmed_verifier.verify_citation",
            return_value={
                "query": "12345[PMID]",
                "match_status": "not_found",
                "pmid": None,
                "title": None,
                "journal": None,
                "year": None,
                "doi": None,
            },
        ):
            not_found_result = run_pipeline(copy.deepcopy(payload))

        with patch(
            "cmo_scientific_engine.pubmed_verifier.verify_citation",
            return_value={
                "query": "12345[PMID]",
                "match_status": "api_unavailable",
                "pmid": None,
                "title": None,
                "journal": None,
                "year": None,
                "doi": None,
                "verification_status": "deferred",
                "error_class": "network_or_proxy",
            },
        ):
            api_unavailable_result = run_pipeline(copy.deepcopy(payload))

        self.assertEqual(
            not_found_result["claim_reference_map"][0]["reference_verification_status"],
            ["FAILED"],
        )
        self.assertEqual(
            api_unavailable_result["claim_reference_map"][0]["reference_verification_status"],
            ["UNVERIFIED"],
        )
        not_found_checks = {
            (item["claim_id"], item["code"])
            for item in not_found_result["failed_checks"]
        }
        api_unavailable_checks = {
            (item["claim_id"], item["code"])
            for item in api_unavailable_result["failed_checks"]
        }
        self.assertIn(("CLM-001", "reference_verification_failed"), not_found_checks)
        self.assertNotIn(("CLM-001", "reference_verification_failed"), api_unavailable_checks)
        self.assertIn(("CLM-001", "unverified_reference"), api_unavailable_checks)

    def test_auditor_rewrites_overclaiming_without_confirmed_rct(self) -> None:
        claims_json = {
            "study": {
                "study_id": "STUDY-002",
                "title": "Association example",
                "domain": "clinical_research",
                "objective": "Assess throughput.",
            },
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "finding_ids": ["FND-001"],
                    "text": "Sleep extension improved median cognitive throughput by 14 percent.",
                    "priority": "primary",
                    "uncertainty": "moderate",
                    "evidence_needed": "RCT",
                    "justification": "Intervention effect claims need controlled causal evidence.",
                }
            ],
        }
        mapping_json = {
            "claim_reference_map": [
                {
                    "claim_id": "CLM-001",
                    "reference_ids": ["REF-001"],
                    "citations": ["Navarro L, Singh P. Randomized trial of cognitive throughput after sleep extension. J Sleep Metrics. 2025;12(4):201-210."],
                    "evidence_match": ["MODERATE"],
                    "reference_verification_status": ["UNVERIFIED"],
                    "mismatch_flags": ["reference_unverified"],
                }
            ]
        }

        result = audit_claims(claims_json, mapping_json)

        self.assertEqual(result["claim_audits"][0]["overclaiming"], "YES")
        self.assertEqual(result["claim_audits"][0]["rewritten_claim_text"], "Sleep extension was associated with improvement in median cognitive throughput by 14 percent.")
        self.assertEqual(result["audit_summary"]["scientific_reliability_score"], 30.0)

    def test_generator_rejects_deprecated_finding_claim_fields(self) -> None:
        payload = self._example_payload()
        payload["findings"][0]["claim_text"] = "Deprecated claim"

        with self.assertRaisesRegex(ValueError, "deprecated keys"):
            run_pipeline(payload)


if __name__ == "__main__":
    unittest.main()
