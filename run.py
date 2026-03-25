"""Official guided CLI entrypoint for Ramón's private scientific drafting assistant."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from cmo_scientific_engine.article_strategy_engine import recommend_article_strategy
from cmo_scientific_engine.free_text_ingest import ingest_free_text
from cmo_scientific_engine.original_article_generator import generate_original_article
from cmo_scientific_engine.pubmed_verifier import verify_citation

ARTICLE_TYPES = {
    "1": ("original_article", "Original article"),
    "2": ("narrative_review", "Narrative review"),
    "3": ("scoping_review", "Scoping review"),
    "4": ("conceptual_article", "Conceptual article"),
    "5": ("editorial_or_commentary", "Editorial / commentary"),
}

LANGUAGES = {
    "1": "Spanish",
    "2": "English",
}

TONES = {
    "1": "concise",
    "2": "rigorous",
    "3": "high-impact",
    "4": "narrative",
    "5": "balanced clinical",
}


def _prompt_choice(prompt: str, options: Dict[str, str | tuple[str, str]]) -> str:
    while True:
        print(prompt)
        for key, value in options.items():
            label = value[1] if isinstance(value, tuple) else value
            print(f"  {key}) {label}")
        selected = input("Select an option: ").strip()
        if selected in options:
            return selected
        print("Invalid option. Please try again.\n")


def _prompt_multiline_text() -> str:
    print("Paste your scientific notes. Press ENTER twice to finish:")
    lines: List[str] = []
    blank_count = 0
    while True:
        line = input()
        if line.strip() == "":
            blank_count += 1
            if blank_count >= 2:
                break
        else:
            blank_count = 0
        lines.append(line)
    return "\n".join(lines).strip()


def _normalize_title(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return "Draft manuscript"
    if compact[-1] not in ".!?":
        compact += "."
    return compact


def _determine_language_key(language: str) -> str:
    return "es" if language.lower().startswith("span") else "en"


def _section_plan(article_type: str, lang_key: str) -> List[str]:
    plans = {
        "original_article": ["Introduction", "Methods", "Results", "Discussion"],
        "narrative_review": ["Introduction", "Current evidence", "Clinical implications", "Discussion"],
        "scoping_review": ["Rationale", "Scope and sources", "Evidence map", "Research gaps"],
        "conceptual_article": ["Conceptual background", "Proposed framework", "Practical application", "Discussion"],
        "editorial_or_commentary": ["Context", "Core argument", "Practical implications", "Closing perspective"],
    }
    if lang_key == "es":
        translated = {
            "Introduction": "Introducción",
            "Methods": "Métodos",
            "Results": "Resultados",
            "Discussion": "Discusión",
            "Current evidence": "Evidencia actual",
            "Clinical implications": "Implicaciones clínicas",
            "Rationale": "Fundamento",
            "Scope and sources": "Alcance y fuentes",
            "Evidence map": "Mapa de evidencia",
            "Research gaps": "Brechas de investigación",
            "Conceptual background": "Marco conceptual",
            "Proposed framework": "Propuesta de marco",
            "Practical application": "Aplicación práctica",
            "Context": "Contexto",
            "Core argument": "Argumento central",
            "Practical implications": "Implicaciones prácticas",
            "Closing perspective": "Perspectiva final",
        }
        return [translated[item] for item in plans[article_type]]
    return plans[article_type]


def _fallback_sections(ingested: Dict[str, Any], article_type: str, lang_key: str) -> Dict[str, str]:
    study = ingested.get("study", {})
    findings = ingested.get("findings", [])
    objective = study.get("objective") or ("Not explicitly reported" if lang_key == "en" else "No reportado explícitamente")
    findings_text = " ".join(item.get("raw_result", "") for item in findings[:4]).strip() or (
        "No clear measurable findings were detected in the input."
        if lang_key == "en"
        else "No se detectaron hallazgos medibles claros en la entrada."
    )
    sections: Dict[str, str] = {}
    for section_name in _section_plan(article_type, lang_key):
        if lang_key == "es":
            sections[section_name] = (
                f"Objetivo base: {objective}. "
                f"Síntesis cauta: {findings_text}. "
                "Este texto es preliminar y requiere validación metodológica."
            )
        else:
            sections[section_name] = (
                f"Base objective: {objective}. "
                f"Conservative synthesis: {findings_text}. "
                "This draft is preliminary and needs methodological validation."
            )
    return sections


def _build_manuscript(
    free_text: str,
    article_type: str,
    article_label: str,
    language: str,
    tone: str,
    target_style: str,
    ingested: Dict[str, Any],
    detected_strategy: Dict[str, Any],
) -> str:
    lang_key = _determine_language_key(language)

    if article_type == "original_article":
        original = generate_original_article(
            text=free_text,
            free_text_ingest_output=ingested,
            article_strategy_output={"recommended_article_type": article_type},
        )
        title = original.get("title") or ("Original article draft" if lang_key == "en" else "Borrador de artículo original")
        sections = {
            "Introduction" if lang_key == "en" else "Introducción": original.get("sections", {}).get("introduction", ""),
            "Methods" if lang_key == "en" else "Métodos": original.get("sections", {}).get("methods", ""),
            "Results" if lang_key == "en" else "Resultados": original.get("sections", {}).get("results", ""),
            "Discussion" if lang_key == "en" else "Discusión": original.get("sections", {}).get("discussion", ""),
        }
    else:
        study_title = ingested.get("study", {}).get("title")
        default_title = "Clinical research draft" if lang_key == "en" else "Borrador de investigación clínica"
        title = study_title or default_title
        sections = _fallback_sections(ingested, article_type, lang_key)

    objective = ingested.get("study", {}).get("objective")
    findings = ingested.get("findings", [])
    if lang_key == "es":
        summary = _normalize_title(
            f"Tipo: {article_label}. Objetivo: {objective or 'no explícito'}. "
            f"Hallazgos detectados: {len(findings)}. Tono solicitado: {tone}."
        )
        limitations_header = "Limitaciones e incertidumbres"
        next_steps_header = "Próximos pasos recomendados"
        next_steps = [
            "Definir comparador, tamaño muestral y análisis estadístico.",
            "Verificar consistencia entre objetivos, resultados y conclusiones.",
            "Añadir referencias clínicas trazables para cada afirmación clave.",
        ]
    else:
        summary = _normalize_title(
            f"Type: {article_label}. Objective: {objective or 'not explicit'}. "
            f"Detected findings: {len(findings)}. Requested tone: {tone}."
        )
        limitations_header = "Limitations and uncertainties"
        next_steps_header = "Next recommended steps"
        next_steps = [
            "Specify comparator, sample size rationale, and statistical plan.",
            "Check consistency across objective, results, and conclusions.",
            "Add traceable clinical references for each key statement.",
        ]

    missing = ingested.get("missing_fields", [])
    uncertainty_line = ", ".join(missing) if missing else ("none flagged" if lang_key == "en" else "sin faltantes críticos")

    lines = [f"# {title}", "", "## Summary", summary, "", f"- Article type: {article_label}", f"- Language: {language}", f"- Target style/journal: {target_style}", f"- Tone: {tone}", ""]

    for name, body in sections.items():
        lines.extend([f"## {name}", body or "", ""])

    lines.extend(
        [
            f"## {limitations_header}",
            f"- Missing or weakly specified elements: {uncertainty_line}",
            "- Interpret conclusions as hypothesis-generating unless independently confirmed.",
            "",
            f"## {next_steps_header}",
        ]
    )
    lines.extend([f"- {item}" for item in next_steps])
    lines.append("")

    detected = detected_strategy.get("recommended_article_type", "unknown")
    if detected != article_type:
        lines.extend(
            [
                "## Internal note",
                f"- User-selected type was preserved as requested.",
                f"- Automatic detector suggested: {detected}.",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _build_audit_report(
    article_type: str,
    article_label: str,
    detected_strategy: Dict[str, Any],
    ingested: Dict[str, Any],
    pubmed_summary: Dict[str, Any],
) -> str:
    findings = ingested.get("findings", [])
    missing = ingested.get("missing_fields", [])
    weaknesses = []
    if "design" in missing:
        weaknesses.append("Study design is not explicit.")
    if "population" in missing:
        weaknesses.append("Target population is not explicit.")
    if "findings" in missing:
        weaknesses.append("No measurable findings were extracted.")
    if not weaknesses:
        weaknesses.append("No major structural weaknesses detected from free-text parsing.")

    overclaiming_warnings = []
    causal_terms = ("causes", "proved", "demonstrates", "elimina", "cura", "causa")
    for item in findings:
        text = str(item.get("raw_result", "")).lower()
        if any(term in text for term in causal_terms):
            overclaiming_warnings.append(f"Potential causal overstatement: {item.get('raw_result', '')}")

    if not overclaiming_warnings:
        overclaiming_warnings.append("No obvious causal overstatement found in extracted findings.")

    detected = detected_strategy.get("recommended_article_type", "unknown")
    mismatch_note = "No mismatch." if detected == article_type else "Mismatch noted; user-selected type preserved."

    lines = [
        "# Draft Audit Report",
        "",
        "## Overview",
        f"- Selected article type: {article_label} ({article_type})",
        f"- Detected article type: {detected}",
        f"- Strategy confidence: {detected_strategy.get('confidence', 'unknown')}",
        f"- Type consistency: {mismatch_note}",
        "",
        "## Major missing elements",
    ]
    if missing:
        lines.extend([f"- {item}" for item in missing])
    else:
        lines.append("- No critical missing elements from ingestion parser.")

    lines.extend(["", "## Methodological weaknesses identified"])
    lines.extend([f"- {item}" for item in weaknesses])

    lines.extend(["", "## Overclaiming warnings"])
    lines.extend([f"- {item}" for item in overclaiming_warnings])

    lines.extend(["", "## Reference verification status"])
    if not pubmed_summary:
        lines.append("- PubMed verification was not requested.")
    else:
        lines.append(f"- Verification attempted: {pubmed_summary.get('attempted', False)}")
        lines.append(f"- Checked items: {pubmed_summary.get('checked_items', 0)}")
        lines.append(f"- Verified matches: {pubmed_summary.get('verified_matches', 0)}")
        lines.append(f"- Ambiguous matches: {pubmed_summary.get('ambiguous_matches', 0)}")
        lines.append(f"- Not found: {pubmed_summary.get('not_found', 0)}")
        if pubmed_summary.get("api_unavailable", 0):
            lines.append(f"- API unavailable responses: {pubmed_summary.get('api_unavailable', 0)}")

    lines.extend(
        [
            "",
            "## How to improve this draft",
            "- Add explicit methodology details: comparator, sample size rationale, and analysis plan.",
            "- Replace broad claims with effect sizes, confidence intervals, and uncertainty qualifiers.",
            "- Align conclusion strength with available evidence and verification status.",
            "",
        ]
    )
    return "\n".join(lines)


def _run_pubmed_check(ingested: Dict[str, Any]) -> Dict[str, Any]:
    findings = ingested.get("findings", [])
    results = []
    for finding in findings[:3]:
        query = finding.get("raw_result", "")
        if not query:
            continue
        results.append({"finding_id": finding.get("finding_id"), "query": query, "result": verify_citation(query)})

    summary = {
        "attempted": True,
        "checked_items": len(results),
        "verified_matches": sum(1 for item in results if item["result"].get("match_status") == "verified"),
        "ambiguous_matches": sum(1 for item in results if item["result"].get("match_status") == "ambiguous"),
        "not_found": sum(1 for item in results if item["result"].get("match_status") == "not_found"),
        "api_unavailable": sum(1 for item in results if item["result"].get("match_status") == "api_unavailable"),
        "details": results,
    }
    return summary


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized[:30] or "draft"


def _confirm_configuration(config: Dict[str, str]) -> bool:
    print("\nPlease confirm your choices:")
    for key, value in config.items():
        print(f"- {key}: {value}")
    response = input("Proceed with generation? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def main() -> None:
    print("=" * 70)
    print("CMO Scientific Writing Assistant (Private Mode)")
    print("Guided drafting for Ramón: paste your study idea and get a practical draft.")
    print("=" * 70)

    free_text = _prompt_multiline_text()
    if not free_text:
        print("No text was provided. Exiting.")
        return

    article_choice = _prompt_choice("\nWhat type of article do you want to generate?", ARTICLE_TYPES)
    language_choice = _prompt_choice("\nChoose output language:", LANGUAGES)
    target_style = input("\nTarget journal or style (free text): ").strip() or "Not specified"
    tone_choice = _prompt_choice("\nChoose tone:", TONES)
    pubmed_verify = input("\nAttempt PubMed verification? [y/N]: ").strip().lower() in {"y", "yes"}

    article_type, article_label = ARTICLE_TYPES[article_choice]
    language = LANGUAGES[language_choice]
    tone = TONES[tone_choice]

    config = {
        "Article type": article_label,
        "Language": language,
        "Target style/journal": target_style,
        "Tone": tone,
        "PubMed verification": "enabled" if pubmed_verify else "disabled",
    }

    if not _confirm_configuration(config):
        print("Generation cancelled.")
        return

    ingested = ingest_free_text(free_text)
    detected_strategy = recommend_article_strategy(free_text)

    manuscript = _build_manuscript(
        free_text=free_text,
        article_type=article_type,
        article_label=article_label,
        language=language,
        tone=tone,
        target_style=target_style,
        ingested=ingested,
        detected_strategy=detected_strategy,
    )

    pubmed_summary: Dict[str, Any] = {}
    if pubmed_verify:
        print("\nRunning PubMed checks on key findings...")
        pubmed_summary = _run_pubmed_check(ingested)

    audit_report = _build_audit_report(
        article_type=article_type,
        article_label=article_label,
        detected_strategy=detected_strategy,
        ingested=ingested,
        pubmed_summary=pubmed_summary,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs") / f"{timestamp}_{_slug(article_type)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    manuscript_path = output_dir / "manuscript.md"
    audit_path = output_dir / "audit_report.md"
    metadata_path = output_dir / "generation_metadata.json"

    metadata = {
        "generated_at_utc": timestamp,
        "selected_article_type": article_type,
        "selected_article_label": article_label,
        "detected_article_type": detected_strategy.get("recommended_article_type"),
        "detected_confidence": detected_strategy.get("confidence"),
        "language": language,
        "target_style": target_style,
        "tone": tone,
        "pubmed_verification_enabled": pubmed_verify,
        "input_summary": {
            "finding_count": len(ingested.get("findings", [])),
            "missing_fields": ingested.get("missing_fields", []),
        },
    }

    manuscript_path.write_text(manuscript, encoding="utf-8")
    audit_path.write_text(audit_report, encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDraft completed.")
    print(f"- Manuscript: {manuscript_path}")
    print(f"- Audit report: {audit_path}")
    print(f"- Metadata: {metadata_path}")

    if pubmed_verify:
        pubmed_path = output_dir / "pubmed_check.json"
        pubmed_path.write_text(json.dumps(pubmed_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"- PubMed check: {pubmed_path}")


if __name__ == "__main__":
    main()
