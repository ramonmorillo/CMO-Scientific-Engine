"""Tests for the CMO Scientific Engine."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from cmo_scientific_engine import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_pipeline_passes_on_example_input(self) -> None:
        payload = json.loads(Path("examples/test_input.json").read_text())
        result = run_pipeline(payload)

        self.assertEqual(result["pipeline_status"], "pass")
        self.assertEqual(result["audit_summary"]["total_claims"], 2)
        self.assertEqual(len(result["claims"]), 2)
        self.assertEqual(len(result["claim_reference_map"]), 2)
        self.assertEqual(
            [claim["evidence_needed"] for claim in result["claims"]],
            ["RCT", "observational"],
        )
        self.assertEqual(result["audit_summary"]["high_quality_evidence_pct"], 100.0)
        self.assertEqual(result["audit_summary"]["weakly_supported_pct"], 0.0)
        self.assertEqual(result["failed_checks"], [])

    def test_reference_mapper_assigns_references_from_finding_overlap(self) -> None:
        payload = json.loads(Path("examples/test_input.json").read_text())
        payload["reference_library"].append(
            {
                "reference_id": "REF-003",
                "citation": "Lopez T. Systematic review of sleep extension performance trials. Sleep Review. 2025;9(2):10-18.",
                "finding_ids": ["FND-001"],
            }
        )
        result = run_pipeline(payload)
        mapped_items = {item["claim_id"]: item for item in result["claim_reference_map"]}

        self.assertEqual(mapped_items["CLM-001"]["reference_ids"], ["REF-001", "REF-003"])
        self.assertEqual(mapped_items["CLM-001"]["evidence_match"], ["HIGH", "MODERATE"])
        self.assertEqual(mapped_items["CLM-001"]["mismatch_flags"], ["none", "partial_evidence_alignment"])
        self.assertEqual(mapped_items["CLM-002"]["reference_ids"], ["REF-002"])
        self.assertEqual(mapped_items["CLM-002"]["mismatch_flags"], ["none"])

    def test_pipeline_fails_when_weak_support_exceeds_threshold(self) -> None:
        payload = json.loads(Path("examples/test_input.json").read_text())
        payload["reference_library"][0]["citation"] = (
            "Navarro L. Framework note on cognitive pathways. Conceptual Models. 2025;12(4):201-210."
        )
        result = run_pipeline(payload)

        self.assertEqual(result["pipeline_status"], "fail")
        self.assertGreater(result["audit_summary"]["weakly_supported_pct"], 30.0)
        self.assertIn(
            {
                "claim_id": "GLOBAL",
                "code": "weak_support_threshold",
                "detail": "weakly_supported_claims_exceed_30_percent",
                "severity": "fail",
            },
            result["failed_checks"],
        )


if __name__ == "__main__":
    unittest.main()
