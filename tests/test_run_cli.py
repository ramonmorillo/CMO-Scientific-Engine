"""Tests for official run.py helper behavior."""

from __future__ import annotations

import unittest

import run


class RunCliTests(unittest.TestCase):
    def test_fallback_sections_contains_validation_warning(self) -> None:
        ingested = {
            "study": {"objective": "Assess protocol adherence"},
            "findings": [{"raw_result": "Adherence improved by 10 percent."}],
        }

        sections = run._fallback_sections(ingested, "narrative_review", "en")

        self.assertIn("Introduction", sections)
        self.assertIn("needs methodological validation", sections["Introduction"])

    def test_audit_report_marks_type_mismatch(self) -> None:
        ingested = {"missing_fields": ["design"], "findings": []}
        report = run._build_audit_report(
            article_type="conceptual_article",
            article_label="Conceptual article",
            detected_strategy={"recommended_article_type": "original_article", "confidence": "moderate"},
            ingested=ingested,
            pubmed_summary={},
        )

        self.assertIn("Mismatch noted", report)
        self.assertIn("design", report)

    def test_run_pubmed_check_handles_empty_findings(self) -> None:
        summary = run._run_pubmed_check({"findings": []})

        self.assertTrue(summary["attempted"])
        self.assertEqual(summary["checked_items"], 0)


if __name__ == "__main__":
    unittest.main()
