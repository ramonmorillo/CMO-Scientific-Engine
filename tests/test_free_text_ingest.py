"""Tests for free-text ingestion."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from cmo_scientific_engine.free_text_ingest import ingest_free_text
from cmo_scientific_engine.pipeline import run_pipeline


class FreeTextIngestTests(unittest.TestCase):
    def test_ingest_spanish_extracts_core_fields(self) -> None:
        text = (
            "Efecto del sueño extendido en trabajadores nocturnos\n"
            "Objetivo: evaluar el impacto de un protocolo de 6 semanas en rendimiento cognitivo. "
            "Ensayo controlado aleatorizado en 120 participantes adultos. "
            "El resultado principal mostró una mejora del 14% en throughput cognitivo (p<0.05)."
        )

        result = ingest_free_text(text)

        self.assertEqual(result["study"]["study_id"], "AUTO-001")
        self.assertEqual(result["study"]["design"], "randomized controlled trial")
        self.assertEqual(result["study"]["duration"], "6 semanas")
        self.assertEqual(result["study"]["domain"], "clinical_research")
        self.assertTrue(result["findings"])
        self.assertEqual(result["findings"][0]["priority"], "primary")
        self.assertIn(result["findings"][0]["uncertainty"], {"low", "moderate", "unknown"})

    def test_ingest_marks_missing_fields_without_invention(self) -> None:
        text = "Preliminary discussion with no explicit design and no measurable findings yet."

        result = ingest_free_text(text)

        self.assertIsNone(result["study"]["objective"])
        self.assertIsNone(result["study"]["design"])
        self.assertIn("objective", result["missing_fields"])
        self.assertIn("design", result["missing_fields"])
        self.assertIn("findings", result["missing_fields"])

    def test_cli_entrypoint_outputs_json(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "cmo_scientific_engine.free_text_ingest",
            "--text",
            "Objective: assess sleep extension in 40 participants. Throughput improved by 12 percent after 8 weeks.",
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout)

        self.assertIn("study", payload)
        self.assertIn("findings", payload)

    def test_pipeline_accepts_free_text_input(self) -> None:
        payload = {
            "free_text": (
                "Objective: assess protocol adherence in shift workers over 6 weeks. "
                "Observational study in 50 participants. "
                "Adherence remained above 90 percent throughout follow-up."
            ),
            "reference_library": [],
        }

        result = run_pipeline(payload)

        self.assertIn("study", result)
        self.assertIn("claims", result)
        self.assertIn("pipeline_status", result)


if __name__ == "__main__":
    unittest.main()
