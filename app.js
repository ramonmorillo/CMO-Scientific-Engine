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

  const study = {
    study_id: "AUTO-001",
    title: extractTitle(rawText),
    objective: firstMatch(normalized, [
      /(?:objective|aim)\s*[:\-]\s*([^\n\.]+)/i,
      /(?:objetivo|propósito|proposito)\s*[:\-]\s*([^\n\.]+)/i,
      /(?:we aimed to|this study aimed to)\s+([^\.]+)/i,
      /(?:el objetivo fue|el estudio busc[oó])\s+([^\.]+)/i,
    ]),
    design: detectDesign(normalized),
    population: firstMatch(normalized, [
      /(?:in|among)\s+([^\.;,]{5,80}?(?:patients|adults|children|participants|subjects))/i,
      /(?:en|entre)\s+([^\.;,]{5,80}?(?:pacientes|adultos|niños|ninos|participantes|sujetos))/i,
    ]),
    duration: firstMatch(normalized, [
      /\b(\d+\s+(?:day|days|week|weeks|month|months|year|years))\b/i,
      /\b(\d+\s+(?:día|días|semana|semanas|mes|meses|año|años))\b/i,
    ]),
  };

  const findings = sentenceCandidates(normalized)
    .filter(isFindingSentence)
    .map((s, i) => ({
      finding_id: `FND-${String(i + 1).padStart(3, "0")}`,
      raw_result: s,
      priority: priority(s),
      uncertainty: uncertainty(s),
    }));

  const missingFields = ["title", "objective", "design", "population", "duration"].filter((f) => !study[f]);
  if (!findings.length) missingFields.push("findings");

  return { study, findings, missing_fields: missingFields };
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

  const sectionNames = isEs
    ? {
        intro: "Introducción",
        methods: "Métodos",
        results: "Resultados",
        discussion: "Discusión",
      }
    : {
        intro: "Introduction",
        methods: "Methods",
        results: "Results",
        discussion: "Discussion",
      };

  const baseIntro = isEs
    ? `Objetivo: ${study.objective || "no explícito"}. Contexto preliminar a validar.`
    : `Objective: ${study.objective || "not explicit"}. Preliminary context pending validation.`;

  const baseMethods = isEs
    ? `Diseño: ${study.design || "no especificado"}. Población: ${study.population || "no especificada"}. Duración: ${study.duration || "no especificada"}.`
    : `Design: ${study.design || "not specified"}. Population: ${study.population || "not specified"}. Duration: ${study.duration || "not specified"}.`;

  const findingsText = findings.length
    ? findings.map((f) => `- ${cautious(f.raw_result, language)}`).join("\n")
    : isEs
      ? "- No se detectaron hallazgos cuantificables en la entrada."
      : "- No quantifiable findings were detected in the input.";

  const discussion = isEs
    ? "Interpretación conservadora: este borrador no sustituye validación metodológica, estadística ni revisión por pares."
    : "Conservative interpretation: this draft does not replace methodological/statistical validation or peer review.";

  const typeLine = isEs
    ? `Tipo seleccionado: ${ARTICLE_LABELS[articleType]} | Tipo detectado: ${ARTICLE_LABELS[strategy.recommended_article_type]}`
    : `Selected type: ${ARTICLE_LABELS[articleType]} | Detected type: ${ARTICLE_LABELS[strategy.recommended_article_type]}`;

  const limitationLine = isEs
    ? `Elementos faltantes: ${missing_fields.length ? missing_fields.join(", ") : "ninguno crítico detectado"}.`
    : `Missing elements: ${missing_fields.length ? missing_fields.join(", ") : "no critical gaps detected"}.`;

  const draft = [
    `# ${title}`,
    "",
    isEs ? "## Resumen operativo" : "## Operational summary",
    typeLine,
    `${isEs ? "Idioma" : "Language"}: ${language === "es" ? "Spanish" : "English"}.`,
    `${isEs ? "Estilo objetivo" : "Target style"}: ${targetStyle || (isEs ? "no especificado" : "not specified")}.`,
    `${isEs ? "Tono" : "Tone"}: ${tone}.`,
    "",
    `## ${sectionNames.intro}`,
    baseIntro,
    "",
    `## ${sectionNames.methods}`,
    baseMethods,
    "",
    `## ${sectionNames.results}`,
    findingsText,
    "",
    `## ${sectionNames.discussion}`,
    discussion,
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
