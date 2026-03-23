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
        self.assertEqual(result["failed_checks"], [])

    def test_claim_and_reference_ids_remain_aligned(self) -> None:
        payload = json.loads(Path("examples/test_input.json").read_text())
        result = run_pipeline(payload)
        mapped_ids = {
            item["claim_id"]: item["reference_ids"]
            for item in result["claim_reference_map"]
        }

        self.assertEqual(mapped_ids["CLM-001"], ["REF-001"])
        self.assertEqual(mapped_ids["CLM-002"], ["REF-002"])


if __name__ == "__main__":
    unittest.main()
