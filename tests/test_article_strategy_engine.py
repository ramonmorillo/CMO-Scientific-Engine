"""Tests for article strategy recommendation module."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from cmo_scientific_engine.article_strategy_engine import recommend_article_strategy


class ArticleStrategyEngineTests(unittest.TestCase):
    def test_recommends_original_article_for_empirical_spanish_text(self) -> None:
        text = (
            "Objetivo: evaluar adherencia en 180 pacientes con diabetes. "
            "Ensayo aleatorizado de 12 semanas con dos brazos. "
            "El desenlace principal mejoró 14% (p<0.05)."
        )

        result = recommend_article_strategy(text)

        self.assertEqual(result["recommended_article_type"], "original_article")
        self.assertIn(result["confidence"], {"moderate", "high"})

    def test_recommends_systematic_review_for_formal_synthesis(self) -> None:
        text = (
            "We will conduct a systematic review using PRISMA. "
            "PubMed, Embase, and Cochrane will be searched. "
            "Eligibility criteria and risk of bias assessment are predefined. "
            "We will compare pooled effect sizes across interventions."
        )

        result = recommend_article_strategy(text)

        self.assertEqual(result["recommended_article_type"], "systematic_review")
        self.assertNotIn("database search strategy", result["missing_elements"])

    def test_recommends_scoping_review_for_broad_mapping(self) -> None:
        text = (
            "This scoping review will map the literature on digital phenotyping in adolescents, "
            "identify research gaps, and chart available evidence domains."
        )

        result = recommend_article_strategy(text)

        self.assertEqual(result["recommended_article_type"], "scoping_review")

    def test_recommends_conceptual_article_for_theoretical_aim(self) -> None:
        text = (
            "We propose a conceptual framework defining resilience phenotypes and "
            "their methodological implications for translational psychiatry."
        )

        result = recommend_article_strategy(text)

        self.assertEqual(result["recommended_article_type"], "conceptual_article")

    def test_recommends_editorial_for_commentary_intent(self) -> None:
        text = (
            "This editorial offers a perspective on AI regulation in clinical practice "
            "and calls for immediate policy action."
        )

        result = recommend_article_strategy(text)

        self.assertEqual(result["recommended_article_type"], "editorial_or_commentary")

    def test_cli_entrypoint_outputs_json(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "cmo_scientific_engine.article_strategy_engine",
            "--text",
            "Narrative review overview of implementation barriers in primary care.",
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout)

        self.assertIn("recommended_article_type", payload)
        self.assertIn("required_elements", payload)


if __name__ == "__main__":
    unittest.main()
