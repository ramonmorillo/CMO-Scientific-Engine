# Expected output orientation (private MVP)

These are not fixed golden files. They describe what should be produced after `python run.py`.

## 1) Original article example

Input file: `examples/original_article_example_input.txt`

Expected result characteristics:
- `manuscript.md` with title, summary, IMRaD-like structure.
- Explicit limitations about missing methodological details.
- `audit_report.md` listing weaknesses and overclaiming checks.
- Optional `pubmed_check.json` if verification is enabled.

## 2) Conceptual article example

Input file: `examples/conceptual_article_example_input.txt`

Expected result characteristics:
- `manuscript.md` with conceptual sections (framework/proposition/application).
- Conservative wording indicating model is preliminary.
- Audit should note if empirical validation details are missing.

## 3) Review example

Input file: `examples/review_example_input.txt`

Expected result characteristics:
- `manuscript.md` with review-oriented sectioning (scope/evidence synthesis/implications).
- Audit should flag missing search strategy specifics if not explicit.
- Next-steps section should recommend tighter eligibility and synthesis criteria.
