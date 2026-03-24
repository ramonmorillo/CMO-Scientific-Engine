"""Article strategy recommendation for the CMO Scientific Engine."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from typing import Callable, Dict, List, Optional

ArticleStrategy = Dict[str, object]

ARTICLE_TYPES = (
    "original_article",
    "systematic_review",
    "scoping_review",
    "narrative_review",
    "conceptual_article",
    "editorial_or_commentary",
)


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    lowered = without_marks.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _has_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _count_matches(text: str, patterns: List[str]) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE))


def _element_map(text: str) -> Dict[str, bool]:
    return {
        "research_question": _has_any(
            text,
            [
                r"\b(objective|aim|question|hypothesis)\b",
                r"\b(objetivo|pregunta|hipotesis)\b",
            ],
        ),
        "population_or_data_source": _has_any(
            text,
            [
                r"\b(participant|patient|cohort|sample|dataset|registry|trial)\b",
                r"\b(participante|paciente|cohorte|muestra|base de datos|registro|ensayo)\b",
                r"\bn\s*=\s*\d+\b",
                r"\b\d+\s+(participants|patients|subjects|adults|children)\b",
                r"\b\d+\s+(participantes|pacientes|adultos|ninos|niños)\b",
            ],
        ),
        "methods_design": _has_any(
            text,
            [
                r"\b(randomized|randomised|rct|observational|cohort|case-control|cross-sectional|prospective|retrospective|experiment)\b",
                r"\b(aleatorizado|ensayo|observacional|cohorte|casos y controles|transversal|prospectivo|retrospectivo|experimento)\b",
                r"\b(methods|metodos|metodologia)\b",
            ],
        ),
        "outcomes_or_variables": _has_any(
            text,
            [
                r"\b(outcome|endpoint|effect|association|improved|reduced|increased|decreased)\b",
                r"\b(resultado|desenlace|efecto|asociacion|mejora|reduccion|aumento|disminucion)\b",
            ],
        ),
        "quantitative_results": _has_any(
            text,
            [
                r"\b\d+(?:[\.,]\d+)?\s*(%|percent|por ciento)\b",
                r"\bp\s*[<=>]\s*0?\.\d+\b",
                r"\b(ci|confidence interval|intervalo de confianza|odds ratio|hazard ratio|rr|mean)\b",
            ],
        ),
        "search_strategy": _has_any(
            text,
            [
                r"\b(systematic review|meta-analysis|prisma|search strategy|database search)\b",
                r"\b(revision sistematica|revisión sistemática|metaanalisis|meta-analisis|estrategia de busqueda|busqueda en bases)\b",
                r"\b(pubmed|embase|scopus|web of science|cochrane)\b",
            ],
        ),
        "inclusion_criteria": _has_any(
            text,
            [
                r"\b(inclusion criteria|exclusion criteria|eligibility|risk of bias|quality assessment)\b",
                r"\b(criterios de inclusion|criterios de exclusion|elegibilidad|riesgo de sesgo|calidad metodologica)\b",
            ],
        ),
        "comparative_synthesis": _has_any(
            text,
            [
                r"\b(compare|comparison|pooled|synthesis|effect size|meta-regression)\b",
                r"\b(comparar|comparacion|combinado|sintesis|tamano del efecto|metarregresion)\b",
            ],
        ),
        "scope_mapping": _has_any(
            text,
            [
                r"\b(scoping review|map the literature|mapping review|evidence map|broad overview|research gaps)\b",
                r"\b(revision de alcance|revisión de alcance|mapear la literatura|mapa de evidencia|pregunta amplia|brechas de investigacion)\b",
            ],
        ),
        "conceptual_framework": _has_any(
            text,
            [
                r"\b(conceptual|theoretical|framework|taxonomy|definition|definitional|model proposal|methodological framework)\b",
                r"\b(conceptual|teorico|teórico|marco|taxonomia|taxonomía|definicion|definición|propuesta de modelo|marco metodologico)\b",
            ],
        ),
        "argumentative_thesis": _has_any(
            text,
            [
                r"\b(editorial|commentary|perspective|opinion|debate|position statement|call to action)\b",
                r"\b(editorial|comentario|perspectiva|opinion|opinión|debate|posicion|posición|llamado a la accion)\b",
            ],
        ),
    }


def _score_types(text: str, elements: Dict[str, bool]) -> Dict[str, int]:
    empirical_bonus = sum(
        1
        for key in (
            "population_or_data_source",
            "methods_design",
            "outcomes_or_variables",
            "quantitative_results",
        )
        if elements[key]
    )

    return {
        "systematic_review": (
            3 * int(elements["search_strategy"])
            + 2 * int(elements["inclusion_criteria"])
            + 2 * int(elements["comparative_synthesis"])
            + _count_matches(text, [r"\bsystematic review\b", r"\brevision sistematica\b", r"\brevisión sistemática\b"])
        ),
        "scoping_review": (
            3 * int(elements["scope_mapping"])
            + int(elements["search_strategy"])
            + int(elements["research_question"])
            + _count_matches(text, [r"\bscoping review\b", r"\brevision de alcance\b", r"\brevisión de alcance\b"])
        ),
        "original_article": (
            2 * int(elements["research_question"]) + empirical_bonus + int(elements["quantitative_results"])
        ),
        "conceptual_article": (
            3 * int(elements["conceptual_framework"])
            + int(elements["research_question"])
            - int(elements["quantitative_results"])
        ),
        "editorial_or_commentary": (
            3 * int(elements["argumentative_thesis"])
            + int(not elements["methods_design"])
            + int(not elements["search_strategy"])
            - int(elements["quantitative_results"])
        ),
        "narrative_review": (
            int(_has_any(text, [r"\bnarrative review\b", r"\bstate of the art\b", r"\boverview\b", r"\brevision narrativa\b", r"\brevisión narrativa\b"]))
            + int(elements["research_question"])
            + int(not elements["quantitative_results"])
            + int(not elements["methods_design"])
        ),
    }


def _required_elements(article_type: str) -> List[str]:
    lookup = {
        "original_article": [
            "explicit research objective",
            "study design",
            "population or dataset",
            "defined outcomes",
        ],
        "systematic_review": [
            "structured review question",
            "database search strategy",
            "eligibility criteria",
            "comparative evidence synthesis plan",
        ],
        "scoping_review": [
            "broad mapping question",
            "scope boundaries",
            "transparent source search approach",
            "evidence charting framework",
        ],
        "narrative_review": [
            "focused topic scope",
            "narrative synthesis lens",
            "source selection rationale",
            "clear thematic structure",
        ],
        "conceptual_article": [
            "definitional or theoretical objective",
            "conceptual framework",
            "logical proposition set",
            "methodological implications",
        ],
        "editorial_or_commentary": [
            "clear argumentative thesis",
            "contextual trigger or controversy",
            "position support points",
            "audience action implication",
        ],
    }
    return lookup[article_type]


def _missing_elements(article_type: str, elements: Dict[str, bool]) -> List[str]:
    checks: Dict[str, List[tuple[str, Callable[[Dict[str, bool]], bool]]]] = {
        "original_article": [
            ("explicit research objective", lambda e: e["research_question"]),
            ("study design", lambda e: e["methods_design"]),
            ("population or dataset", lambda e: e["population_or_data_source"]),
            ("defined outcomes", lambda e: e["outcomes_or_variables"]),
        ],
        "systematic_review": [
            ("structured review question", lambda e: e["research_question"]),
            ("database search strategy", lambda e: e["search_strategy"]),
            ("eligibility criteria", lambda e: e["inclusion_criteria"]),
            ("comparative evidence synthesis plan", lambda e: e["comparative_synthesis"]),
        ],
        "scoping_review": [
            ("broad mapping question", lambda e: e["research_question"] or e["scope_mapping"]),
            ("scope boundaries", lambda e: e["scope_mapping"]),
            ("transparent source search approach", lambda e: e["search_strategy"]),
            ("evidence charting framework", lambda e: e["scope_mapping"]),
        ],
        "narrative_review": [
            ("focused topic scope", lambda e: e["research_question"] or e["scope_mapping"]),
            ("narrative synthesis lens", lambda e: not e["quantitative_results"]),
            ("source selection rationale", lambda e: e["search_strategy"] or e["inclusion_criteria"]),
            ("clear thematic structure", lambda e: e["research_question"] or e["conceptual_framework"]),
        ],
        "conceptual_article": [
            ("definitional or theoretical objective", lambda e: e["conceptual_framework"]),
            ("conceptual framework", lambda e: e["conceptual_framework"]),
            ("logical proposition set", lambda e: e["research_question"] or e["conceptual_framework"]),
            ("methodological implications", lambda e: e["conceptual_framework"]),
        ],
        "editorial_or_commentary": [
            ("clear argumentative thesis", lambda e: e["argumentative_thesis"]),
            ("contextual trigger or controversy", lambda e: e["argumentative_thesis"]),
            ("position support points", lambda e: e["argumentative_thesis"] or e["research_question"]),
            ("audience action implication", lambda e: e["argumentative_thesis"]),
        ],
    }

    return [label for label, predicate in checks[article_type] if not predicate(elements)]


def recommend_article_strategy(text: str) -> ArticleStrategy:
    """Recommend article type and routing metadata from free-text scientific input."""
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    normalized = _normalize(text)
    elements = _element_map(normalized)
    scores = _score_types(normalized, elements)

    # Conservative gating rules.
    if scores["systematic_review"] >= 5:
        recommended = "systematic_review"
    elif scores["scoping_review"] >= 4 and scores["systematic_review"] < 5:
        recommended = "scoping_review"
    elif scores["original_article"] >= 6 and elements["methods_design"] and elements["population_or_data_source"]:
        recommended = "original_article"
    elif scores["conceptual_article"] >= 3 and not elements["quantitative_results"]:
        recommended = "conceptual_article"
    elif scores["editorial_or_commentary"] >= 3 and not elements["methods_design"]:
        recommended = "editorial_or_commentary"
    else:
        recommended = "narrative_review"

    sorted_candidates = sorted(ARTICLE_TYPES, key=lambda name: scores[name], reverse=True)
    alternatives = [name for name in sorted_candidates if name != recommended][:2]

    top_score = scores[recommended]
    second_score = max([scores[name] for name in ARTICLE_TYPES if name != recommended], default=0)
    score_gap = top_score - second_score
    missing = _missing_elements(recommended, elements)

    if top_score >= 6 and score_gap >= 2 and len(missing) <= 1:
        confidence = "high"
    elif top_score >= 3 and score_gap >= 0:
        confidence = "moderate"
    else:
        confidence = "low"

    rationale: List[str] = []
    if recommended == "original_article":
        rationale.append("Empirical design and population indicators are explicit.")
        rationale.append("Outcome-oriented signals support primary data reporting.")
    elif recommended == "systematic_review":
        rationale.append("Text signals formal multi-database evidence synthesis.")
        rationale.append("Comparative rigor cues indicate structured review intent.")
    elif recommended == "scoping_review":
        rationale.append("Question framing is broad and exploratory.")
        rationale.append("Literature mapping language outweighs comparative synthesis language.")
    elif recommended == "conceptual_article":
        rationale.append("Aim is definitional, theoretical, or methodological.")
        rationale.append("No explicit empirical dataset is required in the text.")
    elif recommended == "editorial_or_commentary":
        rationale.append("Argumentative or perspective language dominates.")
        rationale.append("Formal methods and synthesis protocol are not explicit.")
    else:
        rationale.append("Topic synthesis intent appears without formal review protocol.")
        rationale.append("Conservative default applied due to limited methodological specificity.")

    return {
        "recommended_article_type": recommended,
        "confidence": confidence,
        "rationale": rationale,
        "alternative_types": alternatives,
        "required_elements": _required_elements(recommended),
        "missing_elements": missing,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for article strategy recommendation."""
    parser = argparse.ArgumentParser(description="Recommend article type from free-text scientific input")
    parser.add_argument("--text", required=True, help="Scientific idea/summary/abstract in English or Spanish")
    args = parser.parse_args(argv)

    result = recommend_article_strategy(args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
