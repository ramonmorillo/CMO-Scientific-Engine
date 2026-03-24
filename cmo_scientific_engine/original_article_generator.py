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


def _extract_fragment(text: str, patterns: tuple[str, ...]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            fragment = re.sub(r"\s+", " ", match.group(1)).strip(" .;:")
            if fragment:
                return fragment
    return None


def _methods_components(text: str, study: Dict[str, Any]) -> Dict[str, Optional[str]]:
    normalized = re.sub(r"\s+", " ", text).strip()
    intervention = _extract_fragment(
        normalized,
        (
            r"(?:intervention|exposure)\s*[:\-]\s*([^\.;]+)",
            r"(?:intervenci[oó]n|exposici[oó]n)\s*[:\-]\s*([^\.;]+)",
            r"(?:participants received|subjects received)\s+([^\.;]+)",
            r"(?:los participantes recibieron)\s+([^\.;]+)",
        ),
    )
    comparator = _extract_fragment(
        normalized,
        (
            r"(?:comparator|control|comparison)\s*[:\-]\s*([^\.;]+)",
            r"(?:comparador|control|comparaci[oó]n)\s*[:\-]\s*([^\.;]+)",
            r"(?:compared with|versus)\s+([^\.;]+)",
            r"(?:comparado con|frente a)\s+([^\.;]+)",
        ),
    )
    outcomes = _extract_fragment(
        normalized,
        (
            r"(?:primary outcome|primary endpoint|outcome)\s*[:\-]\s*([^\.;]+)",
            r"(?:resultado principal|variable principal|desenlace principal)\s*[:\-]\s*([^\.;]+)",
            r"(?:secondary outcome|secondary endpoint)\s*[:\-]\s*([^\.;]+)",
            r"(?:resultado secundario|desenlace secundario)\s*[:\-]\s*([^\.;]+)",
        ),
    )
    analysis = _extract_fragment(
        normalized,
        (
            r"(?:analysis|statistical analysis)\s*[:\-]\s*([^\.;]+)",
            r"(?:an[aá]lisis|an[aá]lisis estad[ií]stico)\s*[:\-]\s*([^\.;]+)",
            r"(?:using|with)\s+(regression|anova|t-test|cox model|kaplan[- ]meier|chi[- ]square)",
            r"(?:mediante|con)\s+(regresi[oó]n|anova|prueba t|modelo de cox|kaplan[- ]meier|chi[- ]cuadrado)",
        ),
    )
    return {
        "design": study.get("design"),
        "population": study.get("population"),
        "intervention/exposure": intervention,
        "comparator": comparator,
        "duration": study.get("duration"),
        "outcomes": outcomes,
        "analysis": analysis,
    }


def _build_sections(text: str, study: Dict[str, Any], findings: List[Dict[str, Any]], language: str) -> Dict[str, str]:
    objective = study.get("objective")
    methods = _methods_components(text, study)
    missing_methods = [key for key, value in methods.items() if not value]
    background = _extract_fragment(
        text,
        (
            r"(?:background|context)\s*[:\-]\s*([^\n\.]+)",
            r"(?:antecedentes|contexto)\s*[:\-]\s*([^\n\.]+)",
        ),
    )
    rationale = _extract_fragment(
        text,
        (
            r"(?:rationale|justification)\s*[:\-]\s*([^\n\.]+)",
            r"(?:justificaci[oó]n|fundamento)\s*[:\-]\s*([^\n\.]+)",
        ),
    )

    if language == "es":
        intro_parts = [
            f"Antecedentes: {background}." if background else "Antecedentes: no reportados en la entrada.",
            f"Justificación: {rationale}." if rationale else "Justificación: no reportada en la entrada.",
            f"Objetivo: {objective}." if objective else "Objetivo: no reportado en la entrada.",
        ]

        labels = {
            "design": "Diseño",
            "population": "Población",
            "intervention/exposure": "Intervención/exposición",
            "comparator": "Comparador",
            "duration": "Duración",
            "outcomes": "Desenlaces",
            "analysis": "Análisis",
        }
        method_bits = [
            f"{labels[name]}: {value if value else 'faltante en la entrada'}."
            for name, value in methods.items()
        ]
        if missing_methods:
            method_bits.append(f"Componentes faltantes explícitos: {', '.join(missing_methods)}.")

        if findings:
            primary = [_cautious_result_text(item["raw_result"], language) for item in findings if item.get("priority") == "primary"]
            secondary = [_cautious_result_text(item["raw_result"], language) for item in findings if item.get("priority") == "secondary"]
            unknown = [_cautious_result_text(item["raw_result"], language) for item in findings if item.get("priority") == "unknown"]
            result_bits = []
            if primary:
                result_bits.append("Resultados primarios: " + " ".join(f"{line}." for line in primary))
            if secondary:
                result_bits.append("Resultados secundarios: " + " ".join(f"{line}." for line in secondary))
            if unknown:
                result_bits.append("Resultados adicionales: " + " ".join(f"{line}." for line in unknown))
            results = " ".join(result_bits)
        else:
            results = "No se proporcionaron hallazgos cuantificables para la sección de resultados."

        discussion = (
            "Interpretación principal: la evidencia se limita a hallazgos textuales provistos. "
            "Incertidumbre y limitaciones: faltan componentes metodológicos y validación externa. "
            "Posible relevancia: utilidad potencial sujeta a confirmación independiente."
        )
        return {
            "introduction": " ".join(intro_parts),
            "methods": " ".join(method_bits),
            "results": results,
            "discussion": discussion,
        }

    intro_parts = [
        f"Background: {background}." if background else "Background: not reported in input.",
        f"Rationale: {rationale}." if rationale else "Rationale: not reported in input.",
        f"Objective: {objective}." if objective else "Objective: not reported in input.",
    ]
    labels = {
        "design": "Design",
        "population": "Population",
        "intervention/exposure": "Intervention/exposure",
        "comparator": "Comparator",
        "duration": "Duration",
        "outcomes": "Outcomes",
        "analysis": "Analysis",
    }
    method_bits = [f"{labels[name]}: {value if value else 'missing in input'}." for name, value in methods.items()]
    if missing_methods:
        method_bits.append(f"Explicitly missing components: {', '.join(missing_methods)}.")

    if findings:
        primary = [_cautious_result_text(item["raw_result"], language) for item in findings if item.get("priority") == "primary"]
        secondary = [_cautious_result_text(item["raw_result"], language) for item in findings if item.get("priority") == "secondary"]
        unknown = [_cautious_result_text(item["raw_result"], language) for item in findings if item.get("priority") == "unknown"]
        result_bits = []
        if primary:
            result_bits.append("Primary findings: " + " ".join(f"{line}." for line in primary))
        if secondary:
            result_bits.append("Secondary findings: " + " ".join(f"{line}." for line in secondary))
        if unknown:
            result_bits.append("Additional findings: " + " ".join(f"{line}." for line in unknown))
        results = " ".join(result_bits)
    else:
        results = "No quantifiable findings were provided for the results section."

    discussion = (
        "Principal interpretation: evidence is limited to provided textual findings. "
        "Uncertainty and limitations: missing method components and external corroboration remain. "
        "Possible relevance: findings may inform hypotheses pending independent confirmation."
    )
    return {
        "introduction": " ".join(intro_parts),
        "methods": " ".join(method_bits),
        "results": results,
        "discussion": discussion,
    }


def _build_claims(text: str, study: Dict[str, Any], findings: List[Dict[str, Any]], language: str) -> List[Dict[str, str]]:
    methods = _methods_components(text, study)
    claims: List[Dict[str, str]] = []

    def _append_claim(section: str, text_value: str, evidence_needed: str, certainty: str) -> None:
        claims.append(
            {
                "claim_id": f"CLM-{len(claims) + 1:03d}",
                "text": text_value,
                "section": section,
                "evidence_needed": evidence_needed,
                "certainty": certainty,
            }
        )

    if language == "es":
        _append_claim(
            "introduction",
            f"Objetivo declarado: {study.get('objective')}" if study.get("objective") else "No se identificó objetivo explícito",
            "Revisión sistemática y epidemiología contextual",
            "uncertain" if not study.get("objective") else "moderate",
        )
        method_missing = [name for name, value in methods.items() if not value]
        _append_claim(
            "methods",
            "Métodos reportados con faltantes explícitos" if method_missing else "Métodos reportados con componentes identificables",
            "Protocolo detallado y plan analítico preespecificado",
            "low" if method_missing else "moderate",
        )
        for finding in findings:
            _append_claim(
                "results",
                _cautious_result_text(str(finding.get("raw_result", "")), language),
                "Resultados estadísticos, medidas de efecto y datos reproducibles",
                _certainty_from_uncertainty(str(finding.get("uncertainty", "unknown"))),
            )
        _append_claim(
            "discussion",
            "La interpretación se mantiene conservadora y dependiente de validación externa",
            "Validación externa, replicación independiente y triangulación causal",
            "uncertain",
        )
        return claims

    _append_claim(
        "introduction",
        f"Stated objective: {study.get('objective')}" if study.get("objective") else "No explicit objective identified",
        "Systematic background synthesis and epidemiologic context",
        "uncertain" if not study.get("objective") else "moderate",
    )
    method_missing = [name for name, value in methods.items() if not value]
    _append_claim(
        "methods",
        "Methods reported with explicit missing components" if method_missing else "Methods reported with identifiable components",
        "Detailed protocol and prespecified analytic plan",
        "low" if method_missing else "moderate",
    )
    for finding in findings:
        _append_claim(
            "results",
            _cautious_result_text(str(finding.get("raw_result", "")), language),
            "Statistical outputs, effect estimates, and reproducible data",
            _certainty_from_uncertainty(str(finding.get("uncertainty", "unknown"))),
        )
    _append_claim(
        "discussion",
        "Interpretation is conservative and dependent on external validation",
        "External validation, independent replication, and causal triangulation",
        "uncertain",
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

    sections = _build_sections(text, study, findings, language)
    claims = _build_claims(text, study, findings, language)

    missing_elements = []
    for field in ("objective", "design", "population", "duration"):
        if study.get(field) is None:
            missing_elements.append(f"study.{field}")
    for field, value in _methods_components(text, study).items():
        if value is None:
            normalized_field = field.replace("/", "_")
            scoped = f"study.{normalized_field}"
            if scoped not in missing_elements:
                missing_elements.append(scoped)
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
