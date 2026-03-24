"""Original article generation for the CMO Scientific Engine."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, List, Optional

from .free_text_ingest import ingest_free_text


StructuredInput = Dict[str, Any]
ArticleOutput = Dict[str, Any]


SPANISH_HINTS = (
    " el ",
    " la ",
    " los ",
    " las ",
    " estudio ",
    " objetivo ",
    " resultados ",
    " método",
    "método",
    "pacientes",
)


def _detect_language(text: str) -> str:
    lowered = f" {text.lower()} "
    if any(token in lowered for token in SPANISH_HINTS):
        return "es"
    if re.search(r"[áéíóúñ]", lowered):
        return "es"
    return "en"


def _strategy_recommends_original(strategy_output: Dict[str, Any]) -> bool:
    candidates = (
        strategy_output.get("recommended_article_type"),
        strategy_output.get("article_type"),
        strategy_output.get("recommendation"),
        strategy_output.get("target_article_type"),
    )
    normalized = {str(value).strip().lower() for value in candidates if value is not None}
    return "original_article" in normalized


def _certainty_from_uncertainty(uncertainty: str) -> str:
    mapping = {
        "low": "high",
        "moderate": "moderate",
        "high": "low",
        "substantial": "low",
        "exploratory": "uncertain",
        "unknown": "uncertain",
    }
    return mapping.get(str(uncertainty).strip().lower(), "uncertain")


def _cautious_result_text(raw_result: str, language: str) -> str:
    text = re.sub(r"\s+", " ", raw_result).strip()
    if language == "es":
        replacements = (
            (r"\bmejor[aoó]?\b", "se asoció con mejora"),
            (r"\baument[aoó]?\b", "se asoció con incremento"),
            (r"\bdisminuy[óo]?\b", "se asoció con disminución"),
            (r"\breduj[óo]?\b", "se asoció con reducción"),
        )
    else:
        replacements = (
            (r"\bimproved\b", "was associated with improvement in"),
            (r"\bincreased\b", "was associated with an increase in"),
            (r"\bdecreased\b", "was associated with a decrease in"),
            (r"\breduced\b", "was associated with a reduction in"),
        )
    revised = text
    for pattern, replacement in replacements:
        revised, count = re.subn(pattern, replacement, revised, count=1, flags=re.IGNORECASE)
        if count:
            return revised
    return text


def _build_sections(study: Dict[str, Any], findings: List[Dict[str, Any]], language: str) -> Dict[str, str]:
    objective = study.get("objective")
    design = study.get("design")
    population = study.get("population")
    duration = study.get("duration")

    if language == "es":
        intro = (
            f"Este estudio evaluó {objective}."
            if objective
            else "Este borrador requiere un objetivo explícito para contextualizar el estudio."
        )
        method_bits = []
        if design:
            method_bits.append(f"Diseño reportado: {design}.")
        if population:
            method_bits.append(f"Población reportada: {population}.")
        if duration:
            method_bits.append(f"Duración reportada: {duration}.")
        if not method_bits:
            method_bits.append("Métodos incompletos: faltan diseño, población y duración.")
        elif not all([design, population, duration]):
            method_bits.append("Métodos incompletos: algunos componentes no fueron proporcionados.")

        if findings:
            results_lines = [f"Hallazgo {idx + 1}: {_cautious_result_text(item['raw_result'], language)}." for idx, item in enumerate(findings)]
            results = " ".join(results_lines)
        else:
            results = "No se proporcionaron hallazgos cuantificables para la sección de resultados."

        discussion = (
            "Resultados demostrados: solo se reportan hallazgos textuales proporcionados. "
            "Interpretación: la relevancia clínica requiere validación adicional."
        )
        return {
            "introduction": intro,
            "methods": " ".join(method_bits),
            "results": results,
            "discussion": discussion,
        }

    intro = (
        f"This study evaluated {objective}."
        if objective
        else "This draft needs an explicit objective to contextualize the study."
    )
    method_bits = []
    if design:
        method_bits.append(f"Reported design: {design}.")
    if population:
        method_bits.append(f"Reported population: {population}.")
    if duration:
        method_bits.append(f"Reported duration: {duration}.")
    if not method_bits:
        method_bits.append("Methods are incomplete: design, population, and duration are missing.")
    elif not all([design, population, duration]):
        method_bits.append("Methods are incomplete: some components were not provided.")

    if findings:
        results_lines = [f"Finding {idx + 1}: {_cautious_result_text(item['raw_result'], language)}." for idx, item in enumerate(findings)]
        results = " ".join(results_lines)
    else:
        results = "No quantifiable findings were provided for the results section."

    discussion = (
        "Demonstrated results: only provided textual findings are reported. "
        "Interpretation: clinical relevance requires additional validation."
    )
    return {
        "introduction": intro,
        "methods": " ".join(method_bits),
        "results": results,
        "discussion": discussion,
    }


def _build_claims(findings: List[Dict[str, Any]], language: str) -> List[Dict[str, str]]:
    claims = []
    for idx, finding in enumerate(findings):
        text = _cautious_result_text(str(finding.get("raw_result", "")), language)
        if language == "es":
            evidence_needed = "Confirmación con detalles metodológicos y replicación independiente"
        else:
            evidence_needed = "Method detail confirmation and independent replication"
        claims.append(
            {
                "claim_id": f"CLM-{idx + 1:03d}",
                "text": text,
                "section": "results",
                "evidence_needed": evidence_needed,
                "certainty": _certainty_from_uncertainty(str(finding.get("uncertainty", "unknown"))),
            }
        )
    return claims


def generate_original_article(
    text: str,
    free_text_ingest_output: Optional[StructuredInput] = None,
    article_strategy_output: Optional[Dict[str, Any]] = None,
) -> ArticleOutput:
    """Generate a structured original article draft from text and strategy guidance."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        raise ValueError("text must be non-empty")

    language = _detect_language(text)
    ingest_output = free_text_ingest_output or ingest_free_text(text)
    article_strategy_output = article_strategy_output or {}

    study = ingest_output.get("study", {})
    findings = ingest_output.get("findings", [])
    missing_fields = list(ingest_output.get("missing_fields", []))

    sections = _build_sections(study, findings, language)
    claims = _build_claims(findings, language)

    missing_elements = []
    for field in ("objective", "design", "population", "duration"):
        if study.get(field) is None:
            missing_elements.append(f"study.{field}")
    if not findings:
        missing_elements.append("findings")
    for item in missing_fields:
        scoped = item if item.startswith("study.") or item == "findings" else f"study.{item}"
        if scoped not in missing_elements:
            missing_elements.append(scoped)

    warnings = []
    if article_strategy_output and not _strategy_recommends_original(article_strategy_output):
        if language == "es":
            warnings.append("article_strategy_engine no recomienda original_article")
        else:
            warnings.append("article_strategy_engine does not recommend original_article")

    if any(key in missing_elements for key in ("study.design", "study.population", "study.duration")):
        if language == "es":
            warnings.append("La sección de métodos está incompleta")
        else:
            warnings.append("Methods section is incomplete")

    return {
        "article_type": "original_article",
        "title": str(study.get("title") or ("Borrador de artículo original" if language == "es" else "Original article draft")),
        "sections": sections,
        "claims": claims,
        "missing_elements": missing_elements,
        "warnings": warnings,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for original article generation."""
    parser = argparse.ArgumentParser(description="Generate a structured original article draft")
    parser.add_argument("--text", required=True, help="Free-text scientific project description")
    parser.add_argument(
        "--structured-json",
        default=None,
        help="Optional JSON string produced by free_text_ingest",
    )
    parser.add_argument(
        "--strategy-json",
        default=None,
        help="Optional JSON string produced by article_strategy_engine",
    )
    args = parser.parse_args(argv)

    structured_input = json.loads(args.structured_json) if args.structured_json else None
    strategy_input = json.loads(args.strategy_json) if args.strategy_json else None

    output = generate_original_article(
        text=args.text,
        free_text_ingest_output=structured_input,
        article_strategy_output=strategy_input,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
