# CMO Scientific Engine

## Pipeline Overview
CMO Scientific Engine is a four-step, JSON-only scientific drafting pipeline.

1. `manuscript_generator` converts structured study input into normalized claims JSON.
2. `reference_mapper` attaches evidence-backed references to each claim.
3. `auditor` validates reference coverage, identifier consistency, evidence traceability, and scientific support.
4. Merge the three module outputs into one final JSON object.

## Global Operating Rules
- Emit structured JSON only unless a repository task explicitly requires prose.
- Prefer minimal tokens, stable keys, and deterministic field ordering.
- Do not call external executables, remote APIs, or non-stdlib dependencies.
- Reuse the exact IDs produced earlier in the pipeline; never rename claim IDs or reference IDs mid-run.
- Treat `study_id`, `claim_id`, `finding_id`, and `reference_id` as immutable identifiers.
- Never fabricate references, evidence levels, or study details; prefer explicit uncertainty.
- Keep text fields under 20 words where possible while remaining scientifically specific.

## Execution Workflow

### Step 1: Generate Claims JSON
Use `.agents/skills/manuscript_generator/SKILL.md`.
- Input: study metadata, findings, and reference library.
- Output: JSON object with `study`, `claims`, and `generation_notes`.
- Rule: every claim must cite one or more `finding_id` values from the source input.
- Rule: every claim must include `evidence_needed` and `justification`.
- Rule: reject generic or non-testable claim text.

### Step 2: Map References
Use `.agents/skills/reference_mapper/SKILL.md`.
- Input: Step 1 claims JSON plus source `reference_library`.
- Output: JSON object with `claim_reference_map` and `unmapped_claims`.
- Rule: map references only when the underlying `finding_id` evidence overlaps.
- Rule: preserve only source references that exist in the supplied library.
- Rule: assign `evidence_match` and flag mismatches without dropping the reference.

### Step 3: Audit References
Use `.agents/skills/auditor/SKILL.md`.
- Input: Step 1 claims JSON plus Step 2 mapping JSON.
- Output: JSON object with `audit_summary`, `claim_audits`, and `failed_checks`.
- Rule: fail claims that lack references, lack source evidence, contain broken IDs, or exceed weak-support thresholds.
- Rule: warnings are allowed for evidence mismatches but do not override fail conditions.

### Step 4: Merge Results
Combine Steps 1-3 into one final JSON object with this top-level schema:

```json
{
  "study": {},
  "claims": [],
  "claim_reference_map": [],
  "audit_summary": {},
  "claim_audits": [],
  "failed_checks": [],
  "pipeline_status": "pass|fail"
}
```

## Automatic Module Invocation
- If the task is to draft scientific claims from structured study findings, call `manuscript_generator` first.
- If claims already exist and references must be attached, call `reference_mapper`.
- If claims and mappings already exist and consistency must be checked, call `auditor`.
- If the user asks for the full pipeline, run the modules in the exact 1→2→3→4 order above.

## Example Usage
Input file: `examples/test_input.json`

Run locally:

```bash
python scripts/run_cmo_pipeline.py examples/test_input.json examples/test_output.json
```

Expected behavior:
1. Create claim JSON with `evidence_needed` and `justification`.
2. Map references from the same input file with `evidence_match` scoring.
3. Audit scientific support, ID integrity, orphan references, and weak-support thresholds.
4. Write merged JSON to `examples/test_output.json`.

## Output Discipline
- Return JSON objects, not markdown tables.
- Keep strings compact and factual.
- Use arrays instead of free-text paragraphs for multi-item content.
- If a module cannot complete a requirement, emit the failure inside JSON and continue only when IDs remain well-formed.
- Use `severity: fail|warning` in `failed_checks` to distinguish hard failures from scientific cautions.
