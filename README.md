# CMO Scientific Engine (Browser MVP)

CMO Scientific Engine is now a **browser-first private scientific drafting tool**.

The official workflow is a static web app that runs without local Python installation. You can host it on GitHub Pages (recommended) and use it from any modern browser.

---

## Official workflow (no local Python required)

Open the browser app and:

1. Paste free text describing your study/project/article idea.
2. Select article type:
   - Original article
   - Narrative review
   - Scoping review
   - Conceptual article
   - Editorial/commentary
3. Choose language (English/Spanish).
4. Add target journal/style and tone.
5. Click **Generate**.

The app returns:

- A readable manuscript draft.
- A human-readable audit/rigor panel.
- Explicit warnings on uncertainty, missing methods/details, and overclaiming risk.

No JSON or pipeline jargon is required in end-user UX.

---

## Project structure

### Browser app (primary)

- `index.html` — main UI
- `styles.css` — sober academic styling
- `app.js` — browser logic (ingestion heuristics, article routing, draft generation, audit panel)

### Python modules (retained as legacy/specification layer)

These modules are preserved and continue to define core scientific behavior that informed the browser MVP migration:

- `cmo_scientific_engine/free_text_ingest.py`
- `cmo_scientific_engine/article_strategy_engine.py`
- `cmo_scientific_engine/original_article_generator.py`
- `cmo_scientific_engine/auditor.py`
- `cmo_scientific_engine/pubmed_verifier.py`
- `cmo_scientific_engine/pipeline.py`

They are useful as:

- Ground-truth specification for heuristics.
- Future backend/service implementation source.
- Regression reference when strengthening scientific rigor checks.

---

## Quick start (GitHub Pages / static hosting)

### Option A: Open locally in browser

Open `index.html` directly in a browser.

### Option B: Publish on GitHub Pages

1. Push repository to GitHub.
2. In repo settings, enable **Pages**.
3. Select deployment from the repository root (or configured static folder).
4. Open the generated URL.

No Python/Node runtime is required for end users.

---

## PubMed and network verification (optional layer)

The MVP keeps PubMed verification optional and decoupled.

- `app.js` includes a configurable `PUBMED_CONFIG.workerEndpoint`.
- If connected to a Cloudflare Worker (or similar proxy), browser app can send findings for remote verification.
- If not configured, core drafting and audit still run fully in-browser.

This preserves privacy-friendly offline-ish drafting while allowing future evidence checks.

---

## Legacy entrypoints status

- `run.py`: **legacy CLI helper**, non-primary for end users.
- `app.py`: **experimental legacy interface**, non-primary.

Browser app is the official product path.

---

## Current MVP scope

Included now:

- Browser-first UX
- Free-text parsing heuristics
- Article-type routing signals
- Conservative draft generation
- Audit/rigor panel with missing elements + overclaiming checks
- Copy/export convenience actions

Pending for later iterations:

- Stronger methodology extraction parity with all Python behaviors
- Full PubMed worker implementation + robust citation matching
- Advanced audit scoring and traceable evidence linking
- Optional backend orchestration when required

---

## Scientific safety stance

This tool is intentionally conservative:

- Does not fabricate data.
- Surfaces uncertainty and missing methodological details.
- Flags potential overclaiming.
- Produces drafts that require expert validation and peer-review-grade refinement.
