const ARTICLE_LABELS = {
  original_article: "Original article",
  narrative_review: "Narrative review",
  scoping_review: "Scoping review",
  conceptual_article: "Conceptual article",
  editorial_or_commentary: "Editorial / commentary",
};

const PUBMED_CONFIG = {
  workerEndpoint: "",
};

const state = {
  latestDraft: "",
  latestAudit: "",
};

const el = {
  freeText: document.getElementById("freeText"),
  articleType: document.getElementById("articleType"),
  language: document.getElementById("language"),
  targetStyle: document.getElementById("targetStyle"),
  tone: document.getElementById("tone"),
  generateBtn: document.getElementById("generateBtn"),
  resetBtn: document.getElementById("resetBtn"),
  copyBtn: document.getElementById("copyBtn"),
  downloadBtn: document.getElementById("downloadBtn"),
  status: document.getElementById("status"),
  draftOutput: document.getElementById("draftOutput"),
  auditOutput: document.getElementById("auditOutput"),
};

function clean(text) {
  return (text || "").replace(/\s+/g, " ").trim();
}

function firstMatch(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match && match[1]) return clean(match[1]);
  }
  return null;
}

function detectField(text, detectors) {
  let best = { value: null, confidence: "none", evidence: "" };
  for (const d of detectors) {
    const match = text.match(d.pattern);
    if (match && match[1]) {
      const value = clean(match[1]);
      if (!value) continue;
      const candidate = { value, confidence: d.confidence, evidence: d.evidence };
      if (best.confidence === "none" || (best.confidence === "moderate" && d.confidence === "high")) {
        best = candidate;
      }
    }
  }
  return best;
}

function extractTitle(raw) {
  const firstLine = (raw || "").trim().split("\n")[0]?.trim() || "";
  if (!firstLine || firstLine.split(/\s+/).length > 18 || firstLine.endsWith(".")) return null;
  return clean(firstLine);
}

function detectDesign(text) {
  const patterns = [
    [/\b(randomized controlled trial|randomised controlled trial|rct|ensayo aleatorizado|eca)\b/i, "randomized controlled trial"],
    [/\b(observational study|cohort study|case-control|cross-sectional|estudio observacional|cohorte|casos y controles|transversal)\b/i, "observational study"],
    [/\b(systematic review|meta-analysis|revisión sistemática|revision sistematica|metaanálisis|metaanalisis)\b/i, "evidence synthesis"],
  ];
  for (const [pattern, label] of patterns) {
    if (pattern.test(text)) return label;
  }
  return null;
}

function sentenceCandidates(text) {
  return text
    .split(/\n+|(?<!\d)\.(?!\d)|[!?;]+/)
    .map(clean)
    .filter((s) => s.split(/\s+/).length >= 6);
}

function priority(sentence) {
  const l = sentence.toLowerCase();
  if (/(primary|primario|resultado principal)/i.test(l)) return "primary";
  if (/(secondary|secundario|exploratory|exploratorio)/i.test(l)) return "secondary";
  return "unknown";
}

function uncertainty(sentence) {
  const l = sentence.toLowerCase();
  if (/(may|might|possibly|podría|posible)/i.test(l)) return "high";
  if (/(significant|p<|statistically|significativo)/i.test(l)) return "low";
  if (/(suggest|associated|asociad|asociación|asociacion)/i.test(l)) return "moderate";
  return "unknown";
}

function isFindingSentence(sentence) {
  const l = sentence.toLowerCase();
  const signal = /\b\d+(?:[\.,]\d+)?\b|%|percent|por ciento|improved|reduced|increased|decreased|mejor|reduj|aument|disminuy/i;
  return signal.test(l);
}

function ingestFreeText(rawText) {
  const normalized = clean(rawText);
  if (!normalized) throw new Error("Please provide text before generating.");

  const objective = detectField(normalized, [
    { pattern: /(?:objective|aim|primary objective)\s*[:\-]\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit objective label" },
    { pattern: /(?:we aim to|we aimed to|this study aimed to|this review aims to)\s+([^\.]+)/i, confidence: "high", evidence: "authorial objective phrase" },
    { pattern: /(?:objetivo|propósito|proposito)\s*[:\-]\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit objective label" },
    { pattern: /(?:el objetivo fue|el estudio busc[oó]|esta revisión busca)\s+([^\.]+)/i, confidence: "high", evidence: "authorial objective phrase" },
    { pattern: /(?:to evaluate|to assess|to explore|to describe)\s+([^\.]{12,150})/i, confidence: "moderate", evidence: "infinitive objective phrase" },
  ]);

  const methods = detectField(normalized, [
    { pattern: /(?:methods?|methodology)\s*[:\-]\s*([^\n]+)/i, confidence: "high", evidence: "explicit methods label" },
    { pattern: /(?:we conducted|we performed|we carried out)\s+([^\.]+)/i, confidence: "moderate", evidence: "authorial methods phrase" },
    { pattern: /(?:métodos?|metodología)\s*[:\-]\s*([^\n]+)/i, confidence: "high", evidence: "explicit methods label" },
    { pattern: /(?:se realiz[oó]|se llev[oó] a cabo)\s+([^\.]+)/i, confidence: "moderate", evidence: "authorial methods phrase" },
  ]);

  const population = detectField(normalized, [
    { pattern: /(?:population|participants?|patients?|subjects?)\s*[:\-]\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit population label" },
    { pattern: /(?:in|among)\s+([^\.;,\n]{5,120}?(?:patients|adults|children|participants|subjects|people living with hiv|plwh))/i, confidence: "moderate", evidence: "population phrase in sentence" },
    { pattern: /(?:población|participantes|pacientes|sujetos)\s*[:\-]\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit population label" },
    { pattern: /(?:en|entre)\s+([^\.;,\n]{5,120}?(?:pacientes|adultos|niños|ninos|participantes|personas con vih))/i, confidence: "moderate", evidence: "population phrase in sentence" },
  ]);

  const outcomes = detectField(normalized, [
    { pattern: /(?:outcomes?|endpoints?)\s*[:\-]\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit outcome label" },
    { pattern: /(?:primary outcome|secondary outcome)\s*[:\-]?\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit outcome phrase" },
    { pattern: /(?:resulted in|associated with|impact on)\s+([^\.]{8,120})/i, confidence: "moderate", evidence: "outcome-bearing result phrase" },
    { pattern: /(?:desenlaces?|resultados?)\s*[:\-]\s*([^\n\.]+)/i, confidence: "high", evidence: "explicit outcome label" },
  ]);

  const study = {
    study_id: "AUTO-001",
    title: extractTitle(rawText),
    objective: objective.value,
    design: detectDesign(normalized),
    methods_summary: methods.value,
    population: population.value,
    duration: firstMatch(normalized, [
      /\b(\d+\s+(?:day|days|week|weeks|month|months|year|years))\b/i,
      /\b(\d+\s+(?:día|días|semana|semanas|mes|meses|año|años))\b/i,
    ]),
    outcomes: outcomes.value,
  };

  const findings = sentenceCandidates(normalized)
    .filter(isFindingSentence)
    .map((s, i) => ({
      finding_id: `FND-${String(i + 1).padStart(3, "0")}`,
      raw_result: s,
      priority: priority(s),
      uncertainty: uncertainty(s),
    }));

  const detected_fields = {
    objective: objective,
    methods: methods,
    population: population,
    outcomes: outcomes,
    design: { value: study.design, confidence: study.design ? "moderate" : "none", evidence: study.design ? "design keyword match" : "" },
  };

  const missingFields = ["title", "objective", "design", "population", "duration", "outcomes"].filter((f) => !study[f]);
  if (!findings.length) missingFields.push("findings_quantitative");

  return { study, findings, missing_fields: missingFields, detected_fields };
}

function recommendArticleStrategy(text) {
  const t = clean(text).toLowerCase();
  const score = {
    original_article: 0,
    narrative_review: 0,
    scoping_review: 0,
    conceptual_article: 0,
    editorial_or_commentary: 0,
  };

  if (/(objective|aim|objetivo|hypothesis|pregunta)/i.test(t)) score.original_article += 1;
  if (/(randomized|rct|cohort|observational|ensayo|cohorte|trial|patients|pacientes)/i.test(t)) score.original_article += 3;
  if (/(%|p<|odds ratio|hazard ratio|intervalo de confianza|confidence interval)/i.test(t)) score.original_article += 2;

  if (/(narrative review|state of the art|overview|revisión narrativa|revision narrativa)/i.test(t)) score.narrative_review += 3;
  if (/(theme|thematic|panorama|synthesis|síntesis|sintesis)/i.test(t)) score.narrative_review += 1;

  if (/(scoping review|evidence map|research gaps|revisión de alcance|revision de alcance|mapa de evidencia|brechas)/i.test(t)) score.scoping_review += 4;
  if (/(pubmed|embase|scopus|web of science)/i.test(t)) score.scoping_review += 1;

  if (/(conceptual|theoretical|framework|taxonomy|definición|teórico|teorico|marco conceptual)/i.test(t)) score.conceptual_article += 4;

  if (/(editorial|commentary|perspective|opinion|position|debate|comentario|perspectiva)/i.test(t)) score.editorial_or_commentary += 4;
  if (!/(methods|metod|randomized|cohort|trial|ensayo)/i.test(t)) score.editorial_or_commentary += 1;

  const ranking = Object.entries(score).sort((a, b) => b[1] - a[1]);
  const recommended = ranking[0][1] > 0 ? ranking[0][0] : "narrative_review";
  const top = ranking[0][1];
  const second = ranking[1][1];
  const gap = top - second;

  return {
    recommended_article_type: recommended,
    confidence: top >= 5 && gap >= 2 ? "high" : top >= 2 ? "moderate" : "low",
    alternatives: ranking.slice(1, 3).map(([k]) => k),
  };
}

function cautious(sentence, lang) {
  if (lang === "es") {
    return sentence
      .replace(/\bmejor[oó]?\b/i, "se asoció con mejora")
      .replace(/\baument[oó]?\b/i, "se asoció con incremento")
      .replace(/\bdisminuy[oó]?\b/i, "se asoció con disminución")
      .replace(/\breduj[oó]?\b/i, "se asoció con reducción");
  }
  return sentence
    .replace(/\bimproved\b/i, "was associated with improvement in")
    .replace(/\bincreased\b/i, "was associated with an increase in")
    .replace(/\bdecreased\b/i, "was associated with a decrease in")
    .replace(/\breduced\b/i, "was associated with a reduction in");
}

function buildDraft({ input, articleType, language, targetStyle, tone, strategy }) {
  const isEs = language === "es";
  const { study, findings, missing_fields } = input;
  const title =
    study.title ||
    (isEs ? "Borrador científico privado" : "Private scientific draft");

  const findingsText = findings.length
    ? findings.map((f) => `- ${cautious(f.raw_result, language)}`).join("\n")
    : isEs
      ? "- No se aportaron resultados cuantitativos; se reportan salidas esperadas."
      : "- No quantifiable findings were detected in the input.";

  const typeLine = isEs
    ? `Tipo seleccionado: ${ARTICLE_LABELS[articleType]} | Tipo detectado: ${ARTICLE_LABELS[strategy.recommended_article_type]}`
    : `Selected type: ${ARTICLE_LABELS[articleType]} | Detected type: ${ARTICLE_LABELS[strategy.recommended_article_type]}`;

  const fieldConfidence = Object.entries(input.detected_fields || {})
    .map(([k, v]) => {
      const label = k.replace("_", " ");
      if (!v?.value) {
        return isEs
          ? `- ${label}: no detectado; se usó redacción estructural con incertidumbre explícita.`
          : `- ${label}: not detected; structured drafting used explicit uncertainty.`;
      }
      return isEs
        ? `- ${label}: detectado con confianza ${v.confidence}; reescrito en el borrador.`
        : `- ${label}: detected with ${v.confidence} confidence; rewritten below.`;
    })
    .join("\n");

  const hivContext = /(hiv|vih|antiretroviral|polypharmacy|polifarmacia|prescription appropriateness|inappropriate prescribing|beers|stopp|start)/i.test(
    `${study.title || ""} ${study.objective || ""} ${study.population || ""} ${input.findings.map((f) => f.raw_result).join(" ")}`
  )
    ? isEs
      ? "La población con VIH puede presentar polifarmacia, interacciones farmacológicas y riesgo de prescripción potencialmente inapropiada (p. ej., criterios Beers o STOPP/START)."
      : "People living with HIV may face polypharmacy, drug–drug interactions, and potentially inappropriate prescribing risk (e.g., Beers or STOPP/START frameworks)."
    : "";

  const rewrittenObjective = study.objective
    ? study.objective
    : isEs
      ? "Sintetizar el problema y mapear evidencia relevante; detalles no totalmente especificados en la entrada."
      : "To synthesize the problem and map relevant evidence; details were not fully specified in the input.";

  const genericBackground = isEs
    ? `Este borrador estructura la pregunta científica con la información disponible.${hivContext ? ` ${hivContext}` : ""}`
    : `This draft structures the scientific question using available input.${hivContext ? ` ${hivContext}` : ""}`;

  const limitationLine = isEs
    ? `Borrador basado en entrada parcial; completar: ${missing_fields.length ? missing_fields.join(", ") : "sin vacíos críticos detectados"}.`
    : `Draft based on partial input; complete: ${missing_fields.length ? missing_fields.join(", ") : "no critical gaps detected"}.`;

  if (articleType === "scoping_review") {
    const methodsLines = [
      isEs ? "- Diseño: revisión de alcance." : "- Design: scoping review.",
      isEs ? "- Marco metodológico: PRISMA-ScR." : "- Framework: PRISMA-ScR.",
      isEs
        ? `- Fuentes de información: ${study.methods_summary || "bases de datos no totalmente especificadas en la entrada; sugerido PubMed/Embase/Scopus."}`
        : `- Information sources: ${study.methods_summary || "databases not fully specified in input; suggested PubMed/Embase/Scopus."}`,
      isEs
        ? `- Criterios de elegibilidad: ${study.population || "población objetivo no completamente definida"}; incluir tipo de estudio y periodo.`
        : `- Eligibility criteria: ${study.population || "target population not fully defined"}; include study type and timeframe.`,
      isEs
        ? `- Estrategia de charting de datos: extracción por dos revisores, variables clínicas y desenlaces (${study.outcomes || "desenlaces no totalmente especificados"}).`
        : `- Data charting strategy: dual-reviewer extraction of clinical variables and outcomes (${study.outcomes || "outcomes not fully specified"}).`,
    ].join("\n");

    return [
      `# ${title}`,
      "",
      isEs ? "## Resumen operativo" : "## Operational summary",
      typeLine,
      `${isEs ? "Idioma" : "Language"}: ${language === "es" ? "Spanish" : "English"}.`,
      `${isEs ? "Estilo objetivo" : "Target style"}: ${targetStyle || (isEs ? "no especificado" : "not specified")}.`,
      `${isEs ? "Tono" : "Tone"}: ${tone}.`,
      "",
      isEs ? "## Estado de extracción y confianza" : "## Extraction and confidence status",
      fieldConfidence,
      "",
      isEs ? "## Antecedentes y justificación" : "## Background and rationale",
      genericBackground,
      "",
      isEs ? "## Objetivo" : "## Objective",
      rewrittenObjective,
      "",
      isEs ? "## Métodos" : "## Methods",
      methodsLines,
      "",
      isEs ? "## Salidas esperadas" : "## Expected outputs",
      findingsText,
      "",
      isEs ? "## Discusión" : "## Discussion",
      isEs
        ? "Se anticipa heterogeneidad en definiciones de adecuación de prescripción, métricas de interacción y desenlaces clínicos; el mapeo permitirá identificar vacíos de evidencia."
        : "Heterogeneity is expected across prescribing-appropriateness definitions, interaction metrics, and clinical endpoints; mapping should identify evidence gaps.",
      "",
      isEs ? "## Limitaciones" : "## Limitations",
      limitationLine,
    ].join("\n");
  }

  const draft = [
    `# ${title}`,
    "",
    isEs ? "## Resumen operativo" : "## Operational summary",
    typeLine,
    `${isEs ? "Idioma" : "Language"}: ${language === "es" ? "Spanish" : "English"}.`,
    `${isEs ? "Estilo objetivo" : "Target style"}: ${targetStyle || (isEs ? "no especificado" : "not specified")}.`,
    `${isEs ? "Tono" : "Tone"}: ${tone}.`,
    "",
    isEs ? "## Estado de extracción y confianza" : "## Extraction and confidence status",
    fieldConfidence,
    "",
    isEs ? "## Introducción" : "## Introduction",
    genericBackground,
    "",
    isEs ? "## Objetivo" : "## Objective",
    rewrittenObjective,
    "",
    isEs ? "## Métodos" : "## Methods",
    isEs
      ? `Diseño: ${study.design || "no totalmente especificado; inferido según entrada"}. Población: ${study.population || "definición parcial en la entrada"}. Duración: ${study.duration || "no detallada en la entrada"}.`
      : `Design: ${study.design || "not fully specified; inferred from input"}. Population: ${study.population || "partially defined in input"}. Duration: ${study.duration || "not detailed in input"}.`,
    "",
    isEs ? "## Resultados / salidas esperadas" : "## Results / Expected outputs",
    findingsText,
    "",
    isEs ? "## Discusión" : "## Discussion",
    isEs
      ? "Interpretación conservadora con construcción activa: se prioriza coherencia científica y se explicitan incertidumbres cuando faltan especificaciones."
      : "Conservative interpretation with constructive drafting: scientific coherence is prioritized, and uncertainty is explicit where specifications are missing.",
    "",
    isEs ? "## Limitaciones" : "## Limitations",
    limitationLine,
  ].join("\n");

  return draft;
}

function detectOverclaiming(findings) {
  const causal = /(causes?|caused|proves?|elimina|cura|causa|prevents?|prevents?)/i;
  const flagged = findings.filter((f) => causal.test(f.raw_result));
  if (!flagged.length) return ["No explicit causal overclaiming detected in extracted findings."];
  return flagged.map((f) => `Potential overclaim: ${f.raw_result}`);
}

function buildAudit({ input, selectedType, strategy, language }) {
  const isEs = language === "es";
  const mismatch = strategy.recommended_article_type !== selectedType;
  const missing = input.missing_fields;
  const overclaiming = detectOverclaiming(input.findings);
  const confidenceLines = Object.entries(input.detected_fields || {}).map(([k, v]) => {
    const label = k.replace("_", " ");
    return v?.value
      ? `- ${label}: ${v.confidence}`
      : `- ${label}: not detected`;
  });

  const lines = isEs
    ? [
        "# Panel de auditoría y rigor",
        "",
        `- Tipo seleccionado: ${ARTICLE_LABELS[selectedType]} (${selectedType})`,
        `- Tipo detectado automáticamente: ${ARTICLE_LABELS[strategy.recommended_article_type]} (${strategy.recommended_article_type})`,
        `- Confianza de detección: ${strategy.confidence}`,
        `- Posible desajuste tipo seleccionado/detectado: ${mismatch ? "sí" : "no"}`,
        "",
        "## Elementos metodológicos faltantes",
        ...(missing.length ? missing.map((m) => `- ${m}`) : ["- No faltantes críticos detectados por heurísticas."]),
        "",
        "## Confianza de extracción",
        ...(confidenceLines.length ? confidenceLines : ["- Sin datos de confianza disponibles."]),
        "",
        "## Riesgo de sobreafirmación",
        ...overclaiming.map((o) => `- ${o}`),
        "",
        "## Limitaciones del borrador",
        "- Generación heurística; no sustituye validación por expertos.",
        "- Sin verificación bibliográfica automática en este MVP local.",
        "- Sensible a calidad/completitud del texto de entrada.",
        "",
        "## Próximos pasos recomendados",
        "- Añadir comparador, análisis estadístico y justificación de tamaño muestral.",
        "- Ajustar conclusiones al nivel de evidencia disponible.",
        "- Incorporar referencias trazables por afirmación clave.",
      ]
    : [
        "# Audit and rigor panel",
        "",
        `- Selected article type: ${ARTICLE_LABELS[selectedType]} (${selectedType})`,
        `- Automatically detected type: ${ARTICLE_LABELS[strategy.recommended_article_type]} (${strategy.recommended_article_type})`,
        `- Detector confidence: ${strategy.confidence}`,
        `- Possible selected/detected mismatch: ${mismatch ? "yes" : "no"}`,
        "",
        "## Missing methodological elements",
        ...(missing.length ? missing.map((m) => `- ${m}`) : ["- No critical gaps detected by heuristics."]),
        "",
        "## Extraction confidence",
        ...(confidenceLines.length ? confidenceLines : ["- No confidence metadata available."]),
        "",
        "## Overclaiming risk",
        ...overclaiming.map((o) => `- ${o}`),
        "",
        "## Draft limitations",
        "- Heuristic generation; does not replace expert validation.",
        "- No automatic bibliography verification in this local MVP.",
        "- Output quality depends on input detail quality.",
        "",
        "## Recommended next steps",
        "- Add comparator, statistical plan, and sample-size rationale.",
        "- Align conclusion strength with available evidence.",
        "- Add traceable references for each key statement.",
      ];

  return lines.join("\n");
}

async function maybeVerifyWithPubMedProxy(findings) {
  if (!PUBMED_CONFIG.workerEndpoint) return null;
  try {
    const resp = await fetch(PUBMED_CONFIG.workerEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ findings: findings.slice(0, 3) }),
    });
    if (!resp.ok) return { warning: `PubMed proxy failed (${resp.status}).` };
    return await resp.json();
  } catch {
    return { warning: "PubMed proxy unavailable." };
  }
}

function setStatus(msg) {
  el.status.textContent = msg;
}

async function onGenerate() {
  try {
    const text = el.freeText.value;
    if (!clean(text)) throw new Error("Please paste study or project text first.");

    setStatus("Generating draft and audit...");
    el.generateBtn.disabled = true;

    const input = ingestFreeText(text);
    const strategy = recommendArticleStrategy(text);
    const selectedType = el.articleType.value;
    const language = el.language.value;

    const draft = buildDraft({
      input,
      articleType: selectedType,
      language,
      targetStyle: clean(el.targetStyle.value),
      tone: clean(el.tone.value),
      strategy,
    });

    const audit = buildAudit({ input, selectedType, strategy, language });
    const pubmed = await maybeVerifyWithPubMedProxy(input.findings);
    const finalAudit = pubmed ? `${audit}\n\n## PubMed proxy\n${JSON.stringify(pubmed, null, 2)}` : audit;

    state.latestDraft = draft;
    state.latestAudit = finalAudit;
    el.draftOutput.textContent = draft;
    el.auditOutput.textContent = finalAudit;

    setStatus("Done. Review draft and rigor panel.");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  } finally {
    el.generateBtn.disabled = false;
  }
}

function onReset() {
  el.freeText.value = "";
  el.articleType.value = "original_article";
  el.language.value = "en";
  el.targetStyle.value = "";
  el.tone.value = "rigorous";
  state.latestDraft = "";
  state.latestAudit = "";
  el.draftOutput.textContent = "";
  el.auditOutput.textContent = "";
  setStatus("Reset complete.");
}

async function onCopy() {
  if (!state.latestDraft) return setStatus("Nothing to copy yet.");
  await navigator.clipboard.writeText(`${state.latestDraft}\n\n${state.latestAudit}`);
  setStatus("Draft and audit copied to clipboard.");
}

function onDownload() {
  if (!state.latestDraft) return setStatus("Nothing to export yet.");
  const blob = new Blob([`${state.latestDraft}\n\n${state.latestAudit}`], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "cmo-scientific-draft.txt";
  a.click();
  URL.revokeObjectURL(url);
  setStatus("Exported cmo-scientific-draft.txt");
}

el.generateBtn.addEventListener("click", onGenerate);
el.resetBtn.addEventListener("click", onReset);
el.copyBtn.addEventListener("click", onCopy);
el.downloadBtn.addEventListener("click", onDownload);
