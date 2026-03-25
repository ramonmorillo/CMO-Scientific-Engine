# CMO Scientific Writing Assistant (Private Tool for Ramón)

This repository is now a **private, guided scientific drafting assistant** for one expert user: **Ramón**.

It is designed for hospital pharmacy and clinical research workflows where speed matters but scientific caution is essential.

## Who this is for

- Ramón (or one similarly experienced clinician-researcher).
- Users who want to paste free text and receive a practical draft quickly.
- Users who do **not** want to interact with JSON, modules, or pipeline internals.

## Official entrypoint (single source of truth)

Use:

```bash
python run.py
```

`run.py` is the official and supported way to use this tool.

## What the guided flow does

The CLI wizard asks, step by step:
1. Your free-text idea/notes (multi-line paste).
2. Article type:
   - original article
   - narrative review
   - scoping review
   - conceptual article
   - editorial/commentary
3. Output language (Spanish or English).
4. Target journal/style.
5. Desired tone.
6. Whether PubMed verification should be attempted.
7. Final confirmation before generation.

Then it generates a readable draft and saves output files.

## Output files

Each run creates a timestamped folder inside `outputs/`.

Minimum files:
- `manuscript.md` (user-facing draft)
- `audit_report.md` (human-readable quality review)
- `generation_metadata.json` (internal run metadata)

If PubMed verification is enabled:
- `pubmed_check.json`

## Quick start

1. Create/activate your Python environment.
2. Install dependencies from your existing project setup (if any).
3. Run:

```bash
python run.py
```

## Realistic usage example

When prompted, paste something like:

```text
Hospital pharmacist intervention for high-risk antibiotic stewardship.
Objective: evaluate 30-day readmission and treatment appropriateness in adults with severe infections.
Observational cohort in 148 patients over 12 months.
Primary outcome showed a 9% absolute reduction in readmissions.
Secondary outcome suggested improved guideline adherence.
```

Then choose:
- Type: Original article
- Language: Spanish
- Target style: Clinical hospital pharmacy journal
- Tone: Rigorous
- PubMed check: Yes

You will receive saved files under `outputs/<timestamp>_original-article/`.

## What this tool can do

- Produce a conservative first draft from unstructured scientific notes.
- Keep article generation practical and fast.
- Flag missing methodological details and possible overclaiming.
- Provide optional PubMed verification attempts for extracted findings.

## What this tool cannot do

- It cannot replace protocol design, statistical review, or peer review.
- It cannot invent valid data where source details are missing.
- It cannot guarantee PubMed verification (network/API ambiguity can occur).

## Scientific safety stance

This assistant is intentionally conservative:
- No fabricated data.
- No false certainty.
- Missing methods/details are surfaced explicitly.
- Claims should be interpreted as draft language pending expert validation.

## About `app.py`

`app.py` remains in the repository as an **experimental interface**.
It is not the official workflow.
For daily/private use, run only:

```bash
python run.py
```
