"""Tests for original article generator."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from cmo_scientific_engine.free_text_ingest import ingest_free_text
from cmo_scientific_engine.original_article_generator import generate_original_article


class OriginalArticleGeneratorTests(unittest.TestCase):
    def test_generates_spanish_output_with_language_match(self) -> None:
        text = (
            "Impacto de intervención de sueño en personal hospitalario\n"
            "Objetivo: evaluar cambios de rendimiento cognitivo en 8 semanas. "
            "Estudio observacional en 80 participantes adultos. "
            "El resultado principal mostró mejora del 12% en velocidad de respuesta."
        )

        result = generate_original_article(text)

        self.assertEqual(result["article_type"], "original_article")
        self.assertIn("Este estudio", result["sections"]["introduction"])
        self.assertTrue(result["claims"])
        self.assertEqual(result["claims"][0]["section"], "results")
        self.assertIn(result["claims"][0]["certainty"], {"high", "moderate", "low", "uncertain"})

    def test_warns_when_strategy_recommends_non_original(self) -> None:
        text = (
            "Objective: evaluate adherence in shift workers over 6 weeks. "
            "Observational study in 45 participants. "
            "Adherence remained above 90 percent during follow-up."
        )

        result = generate_original_article(
            text,
            article_strategy_output={"recommended_article_type": "review_article"},
        )

        self.assertIn("article_strategy_engine does not recommend original_article", result["warnings"])

    def test_methods_incomplete_explicitly_reported(self) -> None:
        text = "Objective: assess feasibility. Preliminary notes without design details."

        result = generate_original_article(text)

        self.assertIn("Methods are incomplete", result["sections"]["methods"])
        self.assertIn("study.design", result["missing_elements"])
        self.assertIn("Methods section is incomplete", result["warnings"])

    def test_uses_provided_structured_input(self) -> None:
        text = "Texto libre base"
        structured = ingest_free_text(
            "Objective: test endpoint in 4 weeks. Observational study in 30 participants. Endpoint decreased by 10 percent."
        )

        result = generate_original_article(text, free_text_ingest_output=structured)

        self.assertEqual(result["title"], structured["study"]["title"] or "Original article draft")
        self.assertEqual(len(result["claims"]), len(structured["findings"]))

    def test_cli_entrypoint_outputs_json(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "cmo_scientific_engine.original_article_generator",
            "--text",
            "Objective: assess endpoint. Observational study in 20 participants. Endpoint improved by 8 percent.",
            "--strategy-json",
            json.dumps({"recommended_article_type": "original_article"}),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["article_type"], "original_article")
        self.assertIn("sections", payload)


if __name__ == "__main__":
    unittest.main()
