"""Simple local Gradio app for the CMO Scientific Engine."""

from __future__ import annotations

import gradio as gr

from cmo_scientific_engine.free_text_ingest import ingest_free_text
from cmo_scientific_engine.original_article_generator import generate_original_article

try:
    from cmo_scientific_engine.article_strategy_engine import decide_article_strategy
except ImportError:
    from cmo_scientific_engine.article_strategy_engine import (
        recommend_article_strategy as decide_article_strategy,
    )

try:
    from cmo_scientific_engine.auditor import audit_article
except ImportError:

    def audit_article(draft: dict) -> dict:
        """Fallback no-op article audit when module-level audit_article is unavailable."""
        return draft


def _clean_section(value: object, fallback: str = "Not provided.") -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else fallback


def _build_abstract(draft: dict, instruction: str) -> str:
    sections = draft.get("sections", {})
    introduction = _clean_section(sections.get("introduction"), "")
    results = _clean_section(sections.get("results"), "")
    discussion = _clean_section(sections.get("discussion"), "")

    intro_short = introduction.split(".")[0].strip()
    results_short = results.split(".")[0].strip()
    discussion_short = discussion.split(".")[0].strip()

    parts = [part for part in (intro_short, results_short, discussion_short) if part]
    if instruction.strip():
        parts.insert(0, f"Instruction context: {instruction.strip()}")

    abstract = ". ".join(parts).strip()
    if abstract and not abstract.endswith("."):
        abstract += "."
    return abstract or "Abstract could not be generated from the provided input."


def _format_claims(claims: list[dict]) -> str:
    if not claims:
        return "- No explicit claims were generated."
    lines = []
    for claim in claims:
        text = _clean_section(claim.get("text"))
        certainty = _clean_section(claim.get("certainty"), "uncertain")
        lines.append(f"- {text} _(certainty: {certainty})_")
    return "\n".join(lines)


def run_engine(text: str, instruction: str) -> str:
    """Run the core module chain and return a markdown manuscript."""
    text = (text or "").strip()
    instruction = (instruction or "").strip()

    if not text:
        return "Please provide scientific text or ideas before generating an article."

    try:
        structured = ingest_free_text(text)
        strategy = decide_article_strategy(text if not instruction else f"{text}\n\nInstructions: {instruction}")
        draft = generate_original_article(
            text=text,
            free_text_ingest_output=structured,
            article_strategy_output=strategy,
        )
        audited = audit_article(draft)
    except Exception as exc:  # pragma: no cover - defensive UI guard
        return f"An error occurred while generating the article: {exc}"

    title = _clean_section(audited.get("title"), "Untitled Manuscript")
    sections = audited.get("sections", {})
    abstract = _build_abstract(audited, instruction)
    introduction = _clean_section(sections.get("introduction"))
    methods = _clean_section(sections.get("methods"))
    results = _clean_section(sections.get("results"))
    discussion = _clean_section(sections.get("discussion"))
    claims_text = _format_claims(audited.get("claims", []))

    return (
        f"# {title}\n\n"
        f"## Abstract\n{abstract}\n\n"
        f"## Introduction\n{introduction}\n\n"
        f"## Methods\n{methods}\n\n"
        f"## Results\n{results}\n\n"
        f"## Discussion\n{discussion}\n\n"
        f"## Claims / Key findings\n{claims_text}"
    )


demo = gr.Interface(
    fn=run_engine,
    inputs=[
        gr.Textbox(
            label="Scientific text / ideas",
            lines=14,
            placeholder="Paste your scientific notes, findings, or project description...",
        ),
        gr.Textbox(
            label="Instructions (type of article, tone, target journal, etc.)",
            lines=4,
            placeholder="Example: Original article, concise tone, target: clinical journal.",
        ),
    ],
    outputs=gr.Markdown(label="Structured scientific manuscript"),
    title="CMO Scientific Engine – Personal Mode",
    description="Generate scientific articles from free text",
    submit_btn="Generate Article",
    allow_flagging="never",
)


if __name__ == "__main__":
    demo.launch()
