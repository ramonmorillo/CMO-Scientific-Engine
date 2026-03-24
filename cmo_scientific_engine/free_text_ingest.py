"""Free-text ingestion for the CMO Scientific Engine."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, List, Optional


StructuredInput = Dict[str, Any]


STUDY_SCHEMA_KEYS = (
    "study_id",
    "title",
    "objective",
    "design",
    "population",
    "duration",
    "domain",
)

DESIGN_PATTERNS = (
    (r"\b(randomized controlled trial|randomised controlled trial|rct)\b", "randomized controlled trial"),
    (r"\b(ensayo controlado aleatorizado|ensayo aleatorizado|eca)\b", "randomized controlled trial"),
    (r"\b(observational study|cohort study|case-control study|cross-sectional study)\b", "observational study"),
    (r"\b(estudio observacional|estudio de cohorte|estudio de casos y controles|estudio transversal)\b", "observational study"),
    (r"\b(meta-analysis|systematic review)\b", "evidence synthesis"),
    (r"\b(metaanálisis|revision sistematica|revisión sistemática)\b", "evidence synthesis"),
)

OBJECTIVE_PATTERNS = (
    r"(?:objective|aim)\s*[:\-]\s*([^\n\.]+)",
    r"(?:objetivo|propósito|proposito)\s*[:\-]\s*([^\n\.]+)",
    r"(?:we aimed to|this study aimed to)\s+([^\.]+)",
    r"(?:el estudio busc[oó]|el objetivo fue)\s+([^\.]+)",
)

DURATION_PATTERNS = (
    r"\b(\d+\s+(?:day|days|week|weeks|month|months|year|years))\b",
    r"\b(\d+\s+(?:d[ií]a|d[ií]as|semana|semanas|mes|meses|a[nñ]o|a[nñ]os))\b",
)

POPULATION_PATTERNS = (
    r"(?:in|among)\s+([^\.;,]{5,80}?(?:patients|adults|children|participants|workers|subjects))",
    r"(?:en|entre)\s+([^\.;,]{5,80}?(?:pacientes|adultos|ni[nñ]os|participantes|trabajadores|sujetos))",
)

FINDING_SIGNAL_PATTERNS = (
    r"\b\d+(?:[\.,]\d+)?\b",
    r"\b(percent|%|por ciento)\b",
    r"\b(increased|decreased|improved|reduced|higher|lower|associated)\b",
    r"\b(aument[oó]|disminuy[oó]|mejor[oó]|reduj[oó]|mayor|menor|asoci)\w*",
)

HEDGE_HIGH = ("may", "might", "possibly", "possible", "podría", "podria", "posible")
HEDGE_MODERATE = ("suggest", "suggests", "associated", "association", "asociado", "asociación", "asociacion")
HEDGE_LOW = ("significant", "significantly", "p<", "statistically", "significativo", "estadísticamente", "estadisticamente")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _first_match(text: str, patterns: tuple[str, ...]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean(match.group(1))
    return None


def _extract_design(text: str) -> Optional[str]:
    for pattern, label in DESIGN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def _extract_domain(text: str) -> Optional[str]:
    lowered = text.lower()
    if any(token in lowered for token in ("patient", "clinical", "hospital", "participants", "adults", "paciente", "participantes", "adultos", "clinico", "clínico")):
        return "clinical_research"
    if any(token in lowered for token in ("animal", "mouse", "murine", "rat", "raton", "ratón", "murino")):
        return "preclinical"
    if any(token in lowered for token in ("device", "sensor", "algorithm", "wearable", "dispositivo", "algoritmo")):
        return "health_technology"
    return None


def _extract_title(raw_text: str) -> Optional[str]:
    first_line = raw_text.strip().splitlines()[0].strip() if raw_text.strip() else ""
    if not first_line or len(first_line.split()) > 18:
        return None
    if first_line.endswith("."):
        return None
    return _clean(first_line)


def _sentence_candidates(text: str) -> List[str]:
    chunks = re.split(r"\n+|(?<!\d)\.(?!\d)|[!?;]+", text)
    sentences = []
    for chunk in chunks:
        sentence = _clean(chunk)
        if len(sentence.split()) >= 6:
            sentences.append(sentence)
    return sentences


def _is_finding_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    if any(token in lowered for token in ("objective", "objetivo", "aim")) and not any(
        token in lowered for token in ("result", "resultado", "outcome", "mostr", "showed")
    ):
        return False
    if any(token in lowered for token in ("ensayo", "study", "estudio", "trial")) and not any(
        token in lowered for token in ("result", "resultado", "outcome", "improved", "mejor")
    ):
        return False
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in FINDING_SIGNAL_PATTERNS)


def _priority(sentence: str) -> str:
    lowered = sentence.lower()
    if any(token in lowered for token in ("primary", "primario", "principal outcome", "resultado principal")):
        return "primary"
    if any(token in lowered for token in ("secondary", "secundario", "exploratory", "exploratorio")):
        return "secondary"
    return "unknown"


def _uncertainty(sentence: str) -> str:
    lowered = sentence.lower()
    if any(token in lowered for token in HEDGE_HIGH):
        return "high"
    if any(token in lowered for token in HEDGE_LOW):
        return "low"
    if any(token in lowered for token in HEDGE_MODERATE):
        return "moderate"
    return "unknown"


def ingest_free_text(text: str, study_id: str = "AUTO-001") -> StructuredInput:
    """Transform free text into normalized structured JSON for the pipeline."""
    normalized = _clean(text)
    if not normalized:
        raise ValueError("text must be non-empty")

    study: Dict[str, Any] = {
        "study_id": study_id,
        "title": _extract_title(text),
        "objective": _first_match(normalized, OBJECTIVE_PATTERNS),
        "design": _extract_design(normalized),
        "population": _first_match(normalized, POPULATION_PATTERNS),
        "duration": _first_match(normalized, DURATION_PATTERNS),
        "domain": _extract_domain(normalized),
    }

    findings = []
    for sentence in _sentence_candidates(normalized):
        if not _is_finding_sentence(sentence):
            continue
        findings.append(
            {
                "finding_id": f"FND-{len(findings) + 1:03d}",
                "raw_result": sentence,
                "priority": _priority(sentence),
                "uncertainty": _uncertainty(sentence),
            }
        )

    missing_fields = [key for key in STUDY_SCHEMA_KEYS if key != "study_id" and study[key] is None]
    if not findings:
        missing_fields.append("findings")

    return {
        "study": study,
        "findings": findings,
        "missing_fields": missing_fields,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for free text ingestion."""
    parser = argparse.ArgumentParser(description="Ingest free text to CMO structured JSON")
    parser.add_argument("--text", required=True, help="Free-text study description in English or Spanish")
    parser.add_argument("--study-id", default="AUTO-001", help="Study identifier override")
    args = parser.parse_args(argv)

    result = ingest_free_text(args.text, study_id=args.study_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
