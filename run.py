"""CMO Scientific Engine - Personal Mode CLI."""

from cmo_scientific_engine.free_text_ingest import ingest_free_text
from cmo_scientific_engine.article_strategy_engine import recommend_article_strategy
from cmo_scientific_engine.original_article_generator import generate_original_article


def decide_article_strategy(structured, instruction):
    combined_text = " ".join(
        [
            structured.get("study", {}).get("title") or "",
            structured.get("study", {}).get("objective") or "",
            " ".join(item.get("raw_result", "") for item in structured.get("findings", [])),
            instruction,
        ]
    ).strip()
    return recommend_article_strategy(combined_text)


def audit_article(draft):
    issues = []
    for item in draft.get("missing_elements", []):
        issues.append(f"Missing element: {item}")
    for item in draft.get("warnings", []):
        issues.append(f"Warning: {item}")
    return {
        "status": "pass" if not issues else "warning",
        "issues": issues,
        "draft": draft,
    }


def read_multiline_text():
    print("Paste your scientific text (press ENTER twice to finish):")
    lines = []
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


def format_manuscript(structured, strategy, audited, instruction):
    draft = audited["draft"]
    lines = []
    lines.append("CMO Scientific Engine – Personal Mode")
    lines.append("=" * 45)
    lines.append("")
    lines.append(f"Title: {draft.get('title', 'Untitled Manuscript')}")
    lines.append(f"Requested style: {instruction}")
    lines.append(f"Recommended article type: {strategy.get('recommended_article_type', 'unknown')}")
    lines.append(f"Strategy confidence: {strategy.get('confidence', 'unknown')}")
    lines.append("")

    lines.append("ABSTRACT")
    lines.append("-" * 8)
    objective = structured.get("study", {}).get("objective") or "Objective not explicitly provided."
    findings = structured.get("findings", [])
    summary_findings = " ".join(item.get("raw_result", "") for item in findings[:3]).strip()
    if not summary_findings:
        summary_findings = "No extractable quantitative findings were detected in the source text."
    lines.append(f"Objective: {objective}")
    lines.append(f"Results summary: {summary_findings}")
    lines.append("")

    lines.append("INTRODUCTION")
    lines.append("-" * 12)
    lines.append(draft.get("sections", {}).get("introduction", ""))
    lines.append("")

    lines.append("METHODS")
    lines.append("-" * 7)
    lines.append(draft.get("sections", {}).get("methods", ""))
    lines.append("")

    lines.append("RESULTS")
    lines.append("-" * 7)
    lines.append(draft.get("sections", {}).get("results", ""))
    lines.append("")

    lines.append("DISCUSSION")
    lines.append("-" * 10)
    lines.append(draft.get("sections", {}).get("discussion", ""))
    lines.append("")

    lines.append("AUDIT")
    lines.append("-" * 5)
    lines.append(f"Status: {audited['status']}")
    if audited["issues"]:
        for issue in audited["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- No issues detected.")

    return "\n".join(lines)


def main():
    text = read_multiline_text()
    if not text:
        print("No input received. Exiting.")
        return

    instruction = input("Describe the article you want (type, journal, tone): ").strip()

    structured = ingest_free_text(text)
    strategy = decide_article_strategy(structured, instruction)
    draft = generate_original_article(text, structured, strategy)
    audited = audit_article(draft)

    output = format_manuscript(structured, strategy, audited, instruction)
    print("\n" + output)

    with open("output_article.txt", "w", encoding="utf-8") as file:
        file.write(output)

    print("\nSaved manuscript to output_article.txt")


if __name__ == "__main__":
    main()
