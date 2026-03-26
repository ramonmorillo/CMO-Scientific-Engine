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

function splitSentences(text) {
  return (text || "")
    .split(/\n+|(?<!\d)\.(?!\d)|[!?;]+/)
    .map(clean)
    .filter(Boolean);
}

function extractDatabases(text) {
  const labels = [
    { pattern: /\bpubmed\b/i, name: "PubMed" },
    { pattern: /\bembase\b/i, name: "Embase" },
    { pattern: /\bweb of science\b/i, name: "Web of Science" },
    { pattern: /\bscopus\b/i, name: "Scopus" },
    { pattern: /\bcochrane\b/i, name: "Cochrane" },
  ];
  return labels.filter((d) => d.pattern.test(text || "")).map((d) => d.name);
}

function extractSentenceByPattern(text, patterns) {
  const sentences = splitSentences(text);
  for (const sentence of sentences) {
    for (const pattern of patterns) {
      if (pattern.test(sentence)) return sentence;
    }
  }
  return null;
}

function inferWorkingTitle(study) {
  if (study.title) return study.title;
  const objective = study.objective || "";
  const normalized = objective
    .replace(/^to\s+/i, "")
    .replace(/^(identify|characterize|map|evaluate|assess)\s+/i, "$1 ")
    .trim();
  if (!normalized) return "Working scientific draft";
  const compact = normalized.split(/\s+/).slice(0, 16).join(" ");
  return `Working title: ${compact.charAt(0).toUpperCase()}${compact.slice(1)}`;
}

function detectDesign(text) {
  const patterns = [
    [/\b(scoping review|review will follow prisma-scr|prisma-scr|revisión de alcance|revision de alcance)\b/i, "scoping review"],
    [/\b(systematic review|meta-analysis|revisión sistemática|revision sistematica|metaanálisis|metaanalisis)\b/i, "evidence synthesis"],
    [/\b(randomized controlled trial|randomised controlled trial|rct|ensayo aleatorizado|eca)\b/i, "randomized controlled trial"],
    [/\b(observational study|cohort study|case-control|cross-sectional|estudio observacional|cohorte|casos y controles|transversal)\b/i, "observational study"],
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
    { pattern: /(?:we aim to|we aimed to|this study aimed to|this review aims to|this scoping review will)\s+([^\.]+)/i, confidence: "high", evidence: "authorial objective phrase" },
    { pattern: /(?:the objective is to|objective is to)\s+([^\.]+)/i, confidence: "high", evidence: "explicit objective sentence" },
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

  const reportingFramework = detectField(normalized, [
    { pattern: /(PRISMA-ScR[^\.]*)/i, confidence: "high", evidence: "explicit reporting framework mention" },
    { pattern: /(?:follow|using|according to)\s+(PRISMA-ScR[^\.]*)/i, confidence: "high", evidence: "framework phrase" },
  ]);
  const eligibility = detectField(normalized, [
    { pattern: /(?:studies will be included if|eligible studies include|inclusion criteria|eligibility criteria)\s*[:\-]?\s*([^\n]+)/i, confidence: "high", evidence: "eligibility phrase" },
    { pattern: /(?:included if|eligibility)\s+([^\.]+)/i, confidence: "moderate", evidence: "eligibility sentence" },
  ]);
  const dataCharting = detectField(normalized, [
    { pattern: /(?:data extraction|data charting|charting)\s*(?:will include|includes|include)?\s*[:\-]?\s*([^\n]+)/i, confidence: "high", evidence: "data extraction phrase" },
    { pattern: /(?:variables collected|variables assessed)\s*[:\-]?\s*([^\n]+)/i, confidence: "moderate", evidence: "variables sentence" },
  ]);
  const noResultsYet = /(no results available at this stage|no results are available|results are not yet available|sin resultados disponibles)/i.test(normalized);
  const databases = extractDatabases(normalized);
  const contextSentence = extractSentenceByPattern(normalized, [
    /multimorbidity|polypharmacy|drug.?drug interactions|older people living with hiv|beers|stopp\/start|anticholinergic burden|potentially inappropriate medication/i,
  ]);
  const rationaleSentence = extractSentenceByPattern(normalized, [
    /remains unclear|gap|gaps|applicability|complexity|unclear/i,
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
    databases,
    reporting_framework: reportingFramework.value,
    eligibility_criteria: eligibility.value,
    data_extraction_plan: dataCharting.value,
    protocol_like: noResultsYet,
    context: contextSentence,
    rationale: rationaleSentence,
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
    reporting_framework: reportingFramework,
    eligibility_criteria: eligibility,
    data_extraction_plan: dataCharting,
    databases: { value: databases.join(", "), confidence: databases.length ? "high" : "none", evidence: databases.length ? "database keyword match" : "" },
    protocol_like: { value: noResultsYet ? "no results yet statement present" : null, confidence: noResultsYet ? "high" : "none", evidence: noResultsYet ? "explicit stage statement" : "" },
    design: { value: study.design, confidence: study.design ? "moderate" : "none", evidence: study.design ? "design keyword match" : "" },
  };

  const missingFields = ["title", "objective", "design", "population", "outcomes"].filter((f) => !study[f]);
  if (!findings.length) missingFields.push("findings_quantitative");
  if (!study.databases.length) missingFields.push("databases");
  if (!study.eligibility_criteria) missingFields.push("eligibility_criteria");
  if (!study.data_extraction_plan) missingFields.push("data_extraction_plan");

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

  if (/(scoping review|evidence map|research gaps|revisión de alcance|revision de alcance|mapa de evidencia|brechas)/i.test(t)) score.scoping_review += 5;
  if (/(pubmed|embase|scopus|web of science|prisma-scr|eligibility criteria|data extraction|charting)/i.test(t)) score.scoping_review += 3;

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
  const title = inferWorkingTitle(study);

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

  const hivContext = /(hiv|vih|antiretroviral|polypharmacy|polifarmacia|prescription appropriateness|inappropriate prescribing|beers|stopp|start|anticholinergic burden|drug.?drug interaction)/i.test(
    `${study.title || ""} ${study.objective || ""} ${study.population || ""} ${study.context || ""} ${input.findings.map((f) => f.raw_result).join(" ")}`
  )
    ? isEs
      ? "Personas mayores con VIH pueden presentar polifarmacia, interacciones farmacológicas y riesgo de medicación potencialmente inapropiada."
      : "Older people living with HIV may face polypharmacy, drug–drug interactions, and potentially inappropriate medication risk."
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
    const dbLine = study.databases.length ? study.databases.join(", ") : "PubMed, Embase, and Web of Science not clearly specified";
    const resultsStatus = study.protocol_like
      ? isEs
        ? "No hay resultados disponibles en esta etapa; el texto corresponde a un borrador tipo protocolo."
        : "No results are available at this stage; the text behaves as a protocol-like scoping draft."
      : isEs
        ? "Se reportan salidas de mapeo según el texto aportado."
        : "Mapping-oriented outputs are reported from the provided text.";
    const methodsLines = [
      isEs ? "- Diseño: revisión de alcance." : "- Design: scoping review.",
      isEs
        ? `- Marco metodológico: ${study.reporting_framework || "PRISMA-ScR no explicitado; inferido con confianza moderada por patrones de revisión de alcance"}.`
        : `- Reporting framework: ${study.reporting_framework || "PRISMA-ScR not explicitly stated; inferred with moderate confidence from scoping-review patterns"}.`,
      isEs
        ? `- Fuentes de información: ${dbLine}.`
        : `- Information sources / databases: ${dbLine}.`,
      isEs
        ? `- Criterios de elegibilidad: ${study.eligibility_criteria || study.population || "definición parcial; completar criterios explícitos de inclusión/exclusión"}.`
        : `- Eligibility criteria: ${study.eligibility_criteria || study.population || "partially defined; add explicit inclusion/exclusion criteria"}.`,
      isEs
        ? `- Plan de charting / extracción: ${study.data_extraction_plan || "variables y dominios parcialmente definidos en la entrada"}.`
        : `- Data charting / extraction plan: ${study.data_extraction_plan || "variables and domains are only partially defined in input"}.`,
      isEs
        ? "- Síntesis planificada: mapeo descriptivo de herramientas, dominios y estado de validación."
        : "- Planned synthesis approach: descriptive mapping of tools, domains, and validation status.",
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
      isEs ? "## Introducción" : "## Introduction",
      `${genericBackground}${study.context ? ` ${study.context}.` : ""}`,
      "",
      isEs ? "### Racional" : "### Rationale",
      study.rationale || (isEs ? "La aplicabilidad de herramientas generales a VIH no está plenamente establecida." : "Applicability of general-population tools to HIV remains uncertain."),
      "",
      isEs ? "### Objetivo de la revisión" : "### Review objective",
      rewrittenObjective,
      "",
      isEs ? "## Métodos" : "## Methods",
      methodsLines,
      "",
      isEs ? "## Contribución esperada / brechas de conocimiento" : "## Expected contribution / knowledge gaps",
      isEs
        ? "El mapeo puede clarificar lagunas para adaptar criterios de prescripción apropiada en personas mayores con VIH."
        : "This map can clarify HIV-specific gaps and support tailoring a prescription-appropriateness index.",
      "",
      isEs ? "## Salidas planificadas" : "## Planned outputs",
      `- ${resultsStatus}`,
      ...(findings.length ? [findingsText] : []),
      "",
      isEs ? "## Discusión" : "## Discussion",
      isEs
        ? "Se espera heterogeneidad entre criterios (Beers, STOPP/START) y dominios como interacciones fármaco-fármaco o carga anticolinérgica en VIH."
        : "Heterogeneity is expected across tools (Beers, STOPP/START) and domains such as drug–drug interactions and anticholinergic burden in HIV.",
      "",
      isEs ? "## Limitaciones" : "## Limitations",
      `${limitationLine} ${isEs ? "Refinar con detalle metodológico antes de envío." : "Refine with full methodological detail before submission."}`,
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

  const scopingChecks = [
    { key: "objective", ok: !!input.study.objective, label: isEs ? "objetivo de revisión" : "review objective" },
    { key: "framework", ok: !!input.study.reporting_framework, label: isEs ? "marco de reporte (p. ej., PRISMA-ScR)" : "reporting framework (e.g., PRISMA-ScR)" },
    { key: "sources", ok: (input.study.databases || []).length > 0, label: isEs ? "estrategia de fuentes/bases" : "source/database strategy" },
    { key: "eligibility", ok: !!input.study.eligibility_criteria, label: isEs ? "elegibilidad definida" : "eligibility definition" },
    { key: "charting", ok: !!input.study.data_extraction_plan, label: isEs ? "plan de charting/extracción" : "charting/data extraction plan" },
    { key: "protocol_stage", ok: input.study.protocol_like, label: isEs ? "declaración explícita de ausencia de resultados" : "explicit no-results-yet statement" },
  ];

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
        ...(selectedType === "scoping_review"
          ? scopingChecks.map((c) => `- ${c.ok ? "cumple" : "brecha"}: ${c.label}`)
          : missing.length
            ? missing.map((m) => `- ${m}`)
            : ["- No faltantes críticos detectados por heurísticas."]),
        "",
        "## Confianza de extracción",
        ...(confidenceLines.length ? confidenceLines : ["- Sin datos de confianza disponibles."]),
        "",
        "## Riesgo de sobreafirmación",
        ...overclaiming.map((o) => `- ${o}`),
        "",
        "## Limitaciones del borrador",
        "- Generación heurística con extracción constructiva; requiere revisión experta.",
        "- Sin verificación bibliográfica automática en este MVP local.",
        "- Sensible a calidad/completitud del texto de entrada.",
        "",
        "## Próximos pasos recomendados",
        ...(selectedType === "scoping_review"
          ? [
              "- Detallar operadores de búsqueda, periodos y criterios de idioma.",
              "- Definir proceso de selección y resolución de desacuerdos.",
              "- Vincular tabla de variables con plan de síntesis descriptiva.",
            ]
          : ["- Añadir comparador, análisis estadístico y justificación de tamaño muestral."]),
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
        ...(selectedType === "scoping_review"
          ? scopingChecks.map((c) => `- ${c.ok ? "met" : "gap"}: ${c.label}`)
          : missing.length
            ? missing.map((m) => `- ${m}`)
            : ["- No critical gaps detected by heuristics."]),
        "",
        "## Extraction confidence",
        ...(confidenceLines.length ? confidenceLines : ["- No confidence metadata available."]),
        "",
        "## Overclaiming risk",
        ...overclaiming.map((o) => `- ${o}`),
        "",
        "## Draft limitations",
        "- Heuristic but constructive extraction; expert review is still required.",
        "- No automatic bibliography verification in this local MVP.",
        "- Output quality depends on input detail quality.",
        "",
        "## Recommended next steps",
        ...(selectedType === "scoping_review"
          ? [
              "- Specify search operators, date limits, and language restrictions.",
              "- Define screening workflow and disagreement resolution.",
              "- Link variable charting fields to descriptive synthesis outputs.",
            ]
          : ["- Add comparator, statistical plan, and sample-size rationale."]),
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
