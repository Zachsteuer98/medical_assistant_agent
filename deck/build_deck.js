// Builds the business findings deck. Every metric is read from eval/summary_*.md so the
// slides cannot drift from the committed evaluation results.  Run: npm run build
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa6");

const SKILL_SCRIPTS = process.env.PPTX_SKILL_SCRIPTS;
const OUT = path.join(__dirname, "Medical_Assistant_Agent_Findings.pptx");
const EVAL = path.join(__dirname, "..", "eval");
const REPO_URL = "github.com/Zachsteuer98/medical_assistant_agent";

// ---------- data ----------
function parseSummary(file) {
  const lines = fs.readFileSync(path.join(EVAL, file), "utf8").split("\n");
  const start = lines.findIndex((l) => l.startsWith("| config"));
  const header = lines[start].split("|").slice(1, -1).map((s) => s.trim());
  const rows = [];
  for (let i = start + 2; lines[i] && lines[i].startsWith("|"); i++) {
    const cells = lines[i].split("|").slice(1, -1).map((s) => s.trim());
    rows.push(Object.fromEntries(header.map((h, j) => [h, cells[j]])));
  }
  return rows;
}
const approach = parseSummary("summary_approach.md");
const chunks = parseSummary("summary_chunk_size.md");
const byName = (rows, prefix) => {
  const row = rows.find((r) => r.config.startsWith(prefix));
  if (!row) throw new Error(`No eval row starting with ${prefix}`);
  return row;
};
const PLAIN = byName(approach, "Plain LLM");
const PROMPTED = byName(approach, "Prompt-engineered");
const RAG = byName(approach, "RAG");
const C1000 = byName(chunks, "1000-token");
const C200 = byName(chunks, "200-token chunks, k=5");
const C200K25 = byName(chunks, "200-token chunks, k=25");
// The chunk-size summary predates the citation column; these counts were measured from
// eval/results/chunk_size.csv and are recorded in docs/adr/0003-chunk-size.md.
const CHUNK_CITED = { c1000: "6/8", c200: "9/9" };
const num = (v) => Number(v);
const fmt = (v) => num(v).toFixed(2);

// Estimated at OpenAI list prices for gpt-4o-mini ($0.15 / $0.60 per 1M tokens), using
// ~1,500 prompt tokens (system + 5 x 200-token chunks + question) and ~600 output tokens.
const COST_PER_QUESTION = (1500 * 0.15 + 600 * 0.6) / 1e6;

// ---------- theme ----------
const THEME = {
  name: "Clinical Teal",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "17212B", lt1: "FFFFFF", dk2: "0E2A33", lt2: "EDF4F5",
    accent1: "0B6E70", // teal: RAG / primary
    accent2: "3FB8B3", // light teal
    accent3: "E07A5F", // coral: highlight / risk
    accent4: "8896A4", // slate: baselines
    accent5: "F2C14E", // amber
    accent6: "52606D", // muted text
    hlink: "0B6E70", folHlink: "52606D",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Medical Assistant Agent: Business Findings";
pres.author = "Zachary Steuer";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333;
const MARGIN = 0.6;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MARGIN + 0.2, y: 2.2, w: 11.5, h: 1.5, fontSize: 48, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MARGIN + 0.2, y: 3.9, w: 11.0, h: 1.3, fontSize: 22, color: C.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, MARGIN, 0.6, MARGIN],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MARGIN, y: 0.4, w: W - 2 * MARGIN, h: 0.9, fontSize: 30, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Medical Assistant Agent · Portfolio case study", options: { x: MARGIN, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: W - MARGIN - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});

// ---------- helpers ----------
async function iconPng(Icon, hex) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Icon, { color: `#${hex}`, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function iconCircle(slide, Icon, x, y, d, fill = C.accent1, name = "icon") {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: `${name}-circle` });
  const pad = d * 0.24;
  slide.addImage({ data: await iconPng(Icon, HEX.lt1), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, altText: name, objectName: `${name}-glyph` });
}

function card(slide, x, y, w, h, name, fill = C.background2, outline = null) {
  const line = outline ? { color: outline, width: 1 } : { type: "none" };
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line, objectName: name });
}

function text(slide, value, opts) {
  slide.addText(value, { isTextBox: true, margin: 0, valign: "top", ...opts });
}

function statCard(slide, x, y, w, h, big, label, name) {
  card(slide, x, y, w, h, name);
  text(slide, big, { x: x + 0.3, y: y + 0.25, w: w - 0.6, h: 0.95, fontSize: 44, bold: true, color: C.accent1, fontFace: THEME.headFontFace, objectName: `${name}-value` });
  text(slide, label, { x: x + 0.3, y: y + 1.2, w: w - 0.6, h: h - 1.4, fontSize: 14, color: C.text1, objectName: `${name}-label` });
}

const CHART_TEXT = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", titleFontFace: "+mn-lt" };
const CHART_STYLE = {
  ...CHART_TEXT,
  catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent6, catAxisLabelFontSize: 14, valAxisLabelFontSize: 12,
  dataLabelColor: HEX.dk1, dataLabelFontSize: 13, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
  valAxisMinVal: 0, valAxisMaxVal: 5, valAxisMajorUnit: 1, valGridLine: { color: "D9E2E6", size: 0.75 }, catGridLine: { style: "none" },
  showLegend: true, legendPos: "b", legendFontSize: 13, legendColor: HEX.dk1, barGapWidthPct: 60,
};

function bullets(items, size = 16) {
  return items.map((t, i) => ({ text: t, options: { bullet: { indent: 18 }, breakLine: i < items.length - 1, paraSpaceAfter: 10, fontSize: size, color: C.text1 } }));
}

// ---------- slides ----------
async function build() {
  // 1. Title
  pres.addSection({ title: "Overview" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Overview" });
  s.addText("Medical Assistant Agent", { placeholder: "title" });
  s.addText("A retrieval-augmented clinical decision-support assistant that answers from a trusted medical manual and cites the source page for every claim", { placeholder: "body" });
  text(s, "Portfolio case study  ·  Zachary Steuer  ·  November 2026", { x: MARGIN + 0.2, y: 6.4, w: 9, h: 0.4, fontSize: 14, color: C.accent2 });
  await iconCircle(s, fa.FaBookMedical, MARGIN + 0.2, 1.0, 0.95, C.accent1, "title-icon");
  s.addNotes("This deck summarizes the business findings from turning a course RAG prototype into a production-style AI agent: a FastAPI back end, React front end, CI, and a corrected evaluation.");

  // 2. Executive summary
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Overview" });
  s.addText("RAG makes every answer traceable to a trusted source", { placeholder: "title" });
  text(s, bullets([
    "Built a full-stack agent that answers clinical questions only from the Merck Manual and links every claim to its page.",
    `Against a plain LLM, RAG raised groundedness from ${fmt(PLAIN.groundedness)} to ${fmt(RAG.groundedness)} (out of 5) with equally relevant answers.`,
    "It was the only approach that cited sources and refused a question the manual cannot answer.",
    "Main risk: the source is the 2011 edition, so a pilot needs a current reference.",
  ]), { x: MARGIN, y: 1.6, w: 5.6, h: 5.0 });
  const sx = 6.7, sw = 2.85, sh = 2.4, gap = 0.3;
  statCard(s, sx, 1.6, sw, sh, RAG.page_cited_answers, `answers cite manual pages (vs ${PLAIN.page_cited_answers} without RAG)`, "stat-cited");
  statCard(s, sx + sw + gap, 1.6, sw, sh, fmt(RAG.groundedness), `groundedness out of 5 (vs ${fmt(PLAIN.groundedness)} plain LLM)`, "stat-grounded");
  statCard(s, sx, 1.6 + sh + gap, sw, sh, `${RAG.mean_latency_s} s`, "average time to a cited answer", "stat-latency");
  statCard(s, sx + sw + gap, 1.6 + sh + gap, sw, sh, `$${COST_PER_QUESTION.toFixed(4)}`, "estimated model cost per question", "stat-cost");
  s.addNotes("Headline: retrieval does not make answers more fluent, it makes them verifiable. Cost per question is an estimate at OpenAI list prices for gpt-4o-mini; hosting is excluded.");

  // 3. Problem
  pres.addSection({ title: "Problem & solution" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem & solution" });
  s.addText("Clinicians face information overload in critical moments", { placeholder: "title" });
  const problems = [
    [fa.FaLayerGroup, "Volume", "The reference manual alone is 4,114 pages across 23 sections. Finding the right passage takes minutes."],
    [fa.FaStopwatch, "Time pressure", "Emergencies such as sepsis or head trauma need protocol answers in seconds, not after a manual search."],
    [fa.FaScaleBalanced, "Trust", "General chatbots answer fluently but give no source to verify, and may be out of date."],
  ];
  const pw = 3.8, pgap = 0.37;
  for (const [i, [Icon, head, body]] of problems.entries()) {
    const x = MARGIN + i * (pw + pgap);
    card(s, x, 1.7, pw, 3.4, `problem-${i}`);
    await iconCircle(s, Icon, x + 0.35, 2.0, 0.85, C.accent1, `problem-${i}`);
    text(s, head, { x: x + 0.35, y: 3.05, w: pw - 0.7, h: 0.5, fontSize: 22, bold: true, color: C.text1, fontFace: THEME.headFontFace });
    text(s, body, { x: x + 0.35, y: 3.6, w: pw - 0.7, h: 1.4, fontSize: 15, color: C.text1 });
  }
  text(s, "Target questions from the business brief", { x: MARGIN, y: 5.45, w: 8, h: 0.35, fontSize: 14, bold: true, color: C.accent6 });
  const uses = ["Diagnostic assistance", "Drug information", "Treatment plans", "Specialty knowledge", "Critical care protocols"];
  const uw = 2.24;
  uses.forEach((u, i) => {
    const x = MARGIN + i * (uw + 0.2);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 5.9, w: uw, h: 0.55, rectRadius: 0.27, fill: { color: C.background1 }, line: { color: C.accent1, width: 1.25 }, objectName: `use-${i}` });
    text(s, u, { x, y: 5.9, w: uw, h: 0.55, fontSize: 14, color: C.accent1, align: "center", valign: "middle" });
  });
  s.addNotes("Problem framing from the original business context: information overload, time-sensitive decisions, and the need for trusted, current references.");

  // 4. Solution flow
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem & solution" });
  s.addText("Every answer is grounded in the manual and cited", { placeholder: "title" });
  const steps = [
    [fa.FaUserDoctor, "1  Ask", "A clinician types a question in plain language."],
    [fa.FaMagnifyingGlass, "2  Retrieve", "The 5 most relevant passages are found among 19,602 indexed chunks."],
    [fa.FaBrain, "3  Generate", "gpt-4o-mini writes a structured answer from those passages only, citing pages."],
    [fa.FaCircleCheck, "4  Verify", "Each citation is a clickable chip that opens the source passage."],
  ];
  const fw = 2.7, fgap = 0.43;
  for (const [i, [Icon, head, body]] of steps.entries()) {
    const x = MARGIN + i * (fw + fgap);
    card(s, x, 1.7, fw, 2.9, `step-${i}`);
    await iconCircle(s, Icon, x + 0.3, 1.95, 0.75, C.accent1, `step-${i}`);
    text(s, head, { x: x + 0.3, y: 2.85, w: fw - 0.6, h: 0.45, fontSize: 20, bold: true, color: C.text1, fontFace: THEME.headFontFace });
    text(s, body, { x: x + 0.3, y: 3.35, w: fw - 0.6, h: 1.2, fontSize: 14, color: C.text1 });
    if (i < steps.length - 1) {
      s.addShape(pres.shapes.RIGHT_ARROW, { x: x + fw + 0.07, y: 3.0, w: 0.29, h: 0.32, fill: { color: C.accent2 }, line: { type: "none" }, objectName: `arrow-${i}` });
    }
  }
  text(s, "Safety guardrails", { x: MARGIN, y: 4.95, w: 6, h: 0.4, fontSize: 18, bold: true, color: C.text1, fontFace: THEME.headFontFace });
  const guards = [
    [fa.FaShieldHalved, "Refuses when the manual does not contain the answer"],
    [fa.FaFileLines, "Treats source text as reference only, never as instructions"],
    [fa.FaUserShield, "Rate-limited; question text is never logged"],
  ];
  const gw = 3.9;
  for (const [i, [Icon, label]] of guards.entries()) {
    const x = MARGIN + i * (gw + 0.2);
    await iconCircle(s, Icon, x, 5.5, 0.6, C.accent3, `guard-${i}`);
    text(s, label, { x: x + 0.75, y: 5.5, w: gw - 0.85, h: 0.75, fontSize: 14, color: C.text1, valign: "middle" });
  }
  s.addNotes("Retrieval uses maximal marginal relevance so the five passages are diverse, not near-duplicates. Generation runs at temperature 0 for reproducible answers.");

  // 5. Architecture
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem & solution" });
  s.addText("A production-style stack, not a notebook", { placeholder: "title" });
  const box = (x, y, w, h, title, sub, name, fill = C.background2, fg = C.text1) => {
    card(s, x, y, w, h, name, fill);
    text(s, title, { x: x + 0.2, y: y + 0.18, w: w - 0.4, h: 0.45, fontSize: 18, bold: true, color: fg, fontFace: THEME.headFontFace });
    text(s, sub, { x: x + 0.2, y: y + 0.65, w: w - 0.4, h: h - 0.8, fontSize: 14, color: fg });
  };
  const arrow = (x, y, w, name) => s.addShape(pres.shapes.RIGHT_ARROW, { x, y, w, h: 0.3, fill: { color: C.accent2 }, line: { type: "none" }, objectName: name });
  text(s, "Online: answering a question", { x: MARGIN, y: 1.5, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.accent6 });
  box(MARGIN, 1.95, 2.9, 1.6, "React UI", "Chat, citation chips, sources panel", "arch-ui", C.accent1, C.background1);
  arrow(MARGIN + 3.0, 2.6, 0.5, "arch-a1");
  box(MARGIN + 3.6, 1.95, 2.9, 1.6, "FastAPI service", "Validation, rate limiting, typed answers", "arch-api", C.accent1, C.background1);
  arrow(MARGIN + 6.6, 2.6, 0.5, "arch-a2");
  box(MARGIN + 7.2, 1.95, 2.35, 1.6, "Chroma", "Vector index, MiniLM, MMR", "arch-db");
  box(MARGIN + 9.75, 1.95, 2.35, 1.6, "gpt-4o-mini", "Cited answer, temperature 0", "arch-llm");
  text(s, "Offline: building the index", { x: MARGIN, y: 3.9, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.accent6 });
  const pipe = ["Manual PDF", "Strip watermarks & front matter", "Split into 200-token chunks", "Embed locally (no API cost)"];
  const pw2 = 2.6;
  pipe.forEach((p, i) => {
    const x = MARGIN + i * (pw2 + 0.53);
    card(s, x, 4.35, pw2, 0.85, `pipe-${i}`);
    text(s, p, { x: x + 0.15, y: 4.35, w: pw2 - 0.3, h: 0.85, fontSize: 14, color: C.text1, align: "center", valign: "middle" });
    if (i < pipe.length - 1) arrow(x + pw2 + 0.1, 4.62, 0.33, `pipe-a${i}`);
  });
  const quality = [
    [fa.FaFlask, "38 automated tests"],
    [fa.FaCodeBranch, "CI on every push"],
    [fa.FaDocker, "Docker images"],
    [fa.FaUserLock, "Privacy guard in CI"],
  ];
  for (const [i, [Icon, label]] of quality.entries()) {
    const x = MARGIN + i * 3.05;
    await iconCircle(s, Icon, x, 5.65, 0.6, C.accent1, `quality-${i}`);
    text(s, label, { x: x + 0.75, y: 5.65, w: 2.2, h: 0.6, fontSize: 15, bold: true, color: C.text1, valign: "middle" });
  }
  s.addNotes("The licensed manual and its vector index never leave the local machine; CI blocks PDFs, indexes, keys and notebook outputs from the public repo.");

  // 6. Methodology
  pres.addSection({ title: "Evaluation results" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evaluation results" });
  s.addText("Evaluation: 10 questions, scored by an independent judge", { placeholder: "title" });
  card(s, MARGIN, 1.6, 5.1, 5.0, "method-questions");
  text(s, "Question set", { x: MARGIN + 0.35, y: 1.85, w: 4.4, h: 0.45, fontSize: 20, bold: true, color: C.text1, fontFace: THEME.headFontFace });
  const qset = [["5", "queries from the original notebook (sepsis, appendicitis, alopecia, brain injury, fracture)"], ["4", "question types from the business brief (embolism, drug names, arthritis, endocrine)"], ["1", "out-of-scope probe: COVID-19 vaccine dosing, which a 2011 manual cannot contain"]];
  qset.forEach(([n, label], i) => {
    const y = 2.5 + i * 1.3;
    text(s, n, { x: MARGIN + 0.35, y, w: 0.8, h: 0.9, fontSize: 40, bold: true, color: C.accent1, fontFace: THEME.headFontFace });
    text(s, label, { x: MARGIN + 1.2, y: y + 0.05, w: 3.6, h: 1.1, fontSize: 14, color: C.text1 });
  });
  const metrics = [
    ["Context relevance", "Did retrieval find the information needed to answer?"],
    ["Groundedness", "Is every claim in the answer supported by the manual?"],
    ["Answer relevance", "Does the answer fully address the question?"],
  ];
  metrics.forEach(([head, body], i) => {
    const y = 1.6 + i * 1.3;
    card(s, 6.1, y, 6.63, 1.1, `metric-${i}`, C.background1, C.accent2);
    text(s, head, { x: 6.4, y: y + 0.15, w: 6.0, h: 0.4, fontSize: 18, bold: true, color: C.accent1, fontFace: THEME.headFontFace });
    text(s, body, { x: 6.4, y: y + 0.58, w: 6.0, h: 0.45, fontSize: 14, color: C.text1 });
  });
  text(s, "Each metric is scored 1 to 5 by gpt-4o, a stronger model than the gpt-4o-mini generator, so the system never grades its own work. The judge always sees the actual retrieved passages.", { x: 6.1, y: 5.6, w: 6.63, h: 1.0, fontSize: 14, color: C.accent6 });
  s.addNotes("Groundedness for the non-RAG baselines is scored against manual passages retrieved for the same question. It measures traceability to the trusted source, not medical correctness.");

  // 7. Approach chart
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evaluation results" });
  s.addText("RAG is the only approach grounded in the trusted source", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [
    { name: "Groundedness", labels: ["Plain LLM", "Prompt-engineered", "RAG"], values: [PLAIN, PROMPTED, RAG].map((r) => num(r.groundedness)) },
    { name: "Answer relevance", labels: ["Plain LLM", "Prompt-engineered", "RAG"], values: [PLAIN, PROMPTED, RAG].map((r) => num(r.answer_relevance)) },
  ], { x: MARGIN, y: 1.5, w: 7.4, h: 5.2, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent1, HEX.accent4], showTitle: true, title: "Mean judge score (1-5), 9 answerable questions", titleFontSize: 14, titleColor: HEX.accent6, ...CHART_STYLE, objectName: "chart-approach" });
  card(s, 8.4, 1.6, 4.33, 5.0, "approach-commentary");
  text(s, bullets([
    `Groundedness: RAG ${fmt(RAG.groundedness)} vs ${fmt(PLAIN.groundedness)} (plain) and ${fmt(PROMPTED.groundedness)} (prompted).`,
    `All three answer the question well (${fmt(PROMPTED.answer_relevance)} to ${fmt(PLAIN.answer_relevance)}). The difference is verifiability, not fluency.`,
    "Prompt engineering lowered groundedness: asking for current guidelines pushed answers beyond the source.",
  ], 15), { x: 8.7, y: 1.9, w: 3.75, h: 4.5 });
  s.addNotes("Same model and temperature for all three approaches; only the method changes. Answer relevance is near-ceiling for everyone, so it does not separate the approaches.");

  // 8. Trust signals table
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evaluation results" });
  s.addText("Only RAG cites its sources and knows when to refuse", { placeholder: "title" });
  const hdr = (t, rag = false) => ({ text: t, options: { bold: true, fontSize: 16, color: rag ? C.background1 : C.text1, fill: { color: rag ? C.accent1 : C.background2 }, align: "center", valign: "middle" } });
  const cell = (t, rag = false) => ({ text: t, options: { fontSize: 16, color: rag ? C.accent1 : C.text1, bold: rag, align: "center", valign: "middle", fill: { color: rag ? C.background2 : C.background1 } } });
  const rowLabel = (t) => ({ text: t, options: { fontSize: 16, color: C.text1, valign: "middle", fill: { color: C.background1 } } });
  const refusal = (r) => (r.correct_refusals.startsWith("1") ? "Refused" : "Answered anyway");
  s.addTable([
    [hdr(""), hdr("Plain LLM"), hdr("Prompt-engineered"), hdr("RAG", true)],
    [rowLabel("Answers citing manual pages"), cell(PLAIN.page_cited_answers), cell(PROMPTED.page_cited_answers), cell(RAG.page_cited_answers, true)],
    [rowLabel("Out-of-scope question (post-2011)"), cell(refusal(PLAIN)), cell(refusal(PROMPTED)), cell(refusal(RAG), true)],
    [rowLabel("Average response time"), cell(`${PLAIN.mean_latency_s} s`), cell(`${PROMPTED.mean_latency_s} s`), cell(`${RAG.mean_latency_s} s`, true)],
  ], { x: MARGIN, y: 1.6, w: W - 2 * MARGIN, colW: [3.9, 2.73, 2.73, 2.77], rowH: 0.75, border: { type: "solid", pt: 1, color: "D9E2E6" }, objectName: "table-trust" });
  card(s, MARGIN, 5.0, W - 2 * MARGIN, 1.6, "covid-callout");
  await iconCircle(s, fa.FaTriangleExclamation, MARGIN + 0.35, 5.4, 0.8, C.accent3, "covid");
  text(s, [
    { text: "Asked about COVID-19 vaccine dosing, ", options: { bold: true } },
    { text: "a topic a 2011 manual cannot contain, both non-RAG models produced confident dosing schedules from training data. RAG replied that the manual does not cover it." },
  ], { x: MARGIN + 1.45, y: 5.2, w: 10.4, h: 1.2, fontSize: 16, color: C.text1, valign: "middle" });
  s.addNotes("The non-RAG dosing answers may even be accurate, but nobody can verify them against the trusted reference. RAG is faster because it writes shorter, source-bound answers.");

  // 9. Chunk-size tuning
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evaluation results" });
  s.addText("Smaller chunks fixed a hidden retrieval flaw", { placeholder: "title" });
  card(s, MARGIN, 1.6, 4.4, 5.0, "chunk-insight");
  await iconCircle(s, fa.FaMagnifyingGlass, MARGIN + 0.35, 1.9, 0.75, C.accent3, "chunk-insight");
  text(s, "The embedding model reads only the first 256 tokens of each passage", { x: MARGIN + 0.35, y: 2.8, w: 3.7, h: 1.0, fontSize: 18, bold: true, color: C.text1, fontFace: THEME.headFontFace });
  text(s, bullets([
    "With the prototype's 1,000-token chunks, about 75% of each passage never influenced search.",
    `200-token chunks: cited answers ${CHUNK_CITED.c1000} to ${CHUNK_CITED.c200}, response time ${C1000.mean_latency_s} s to ${C200.mean_latency_s} s.`,
    "The drug-names question went from \"not found\" to listing trade names.",
  ], 14), { x: MARGIN + 0.35, y: 3.85, w: 3.75, h: 2.7 });
  s.addChart(pres.charts.BAR, [
    { name: "Context relevance", labels: ["1,000 tokens, 5 chunks", "200 tokens, 5 chunks", "200 tokens, 25 chunks"], values: [C1000, C200, C200K25].map((r) => num(r.context_relevance)) },
    { name: "Answer relevance", labels: ["1,000 tokens, 5 chunks", "200 tokens, 5 chunks", "200 tokens, 25 chunks"], values: [C1000, C200, C200K25].map((r) => num(r.answer_relevance)) },
  ], { x: 5.3, y: 1.5, w: 7.43, h: 5.2, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent2, HEX.accent1], showTitle: true, title: "Mean judge score (1-5) by chunking setup", titleFontSize: 14, titleColor: HEX.accent6, ...CHART_STYLE, objectName: "chart-chunks" });
  s.addNotes("Adopted 200-token chunks with 5 per answer as the default (ADR 0003). 25 small chunks retrieved the most relevant text but diluted the answer. About 70% fewer prompt tokens per question.");

  // 10. Prototype corrections
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evaluation results" });
  s.addText("The rebuilt evaluation fixed four flaws in the prototype", { placeholder: "title" });
  const flaws = [
    ["Judge never saw the sources", "It scored answers against a placeholder string, so groundedness was meaningless."],
    ["The generator graded itself", "The same model wrote and judged answers, inviting self-preference bias."],
    ["Wrong prompt evaluated", "Scored answers came from a simpler prompt than the one in production."],
    ["Stale output reported", "Query 5 displayed the brain-injury answer instead of the leg-fracture answer."],
  ];
  const cw = 5.91, ch = 1.75;
  for (const [i, [head, body]] of flaws.entries()) {
    const x = MARGIN + (i % 2) * (cw + 0.3);
    const y = 1.6 + Math.floor(i / 2) * (ch + 0.3);
    card(s, x, y, cw, ch, `flaw-${i}`);
    await iconCircle(s, fa.FaBug, x + 0.3, y + 0.35, 0.7, C.accent3, `flaw-${i}`);
    text(s, head, { x: x + 1.2, y: y + 0.35, w: cw - 1.5, h: 0.5, fontSize: 18, bold: true, color: C.text1, fontFace: THEME.headFontFace });
    text(s, body, { x: x + 1.2, y: y + 0.9, w: cw - 1.5, h: 1.0, fontSize: 14, color: C.text1 });
  }
  text(s, "The prototype reported near-perfect scores of about 5.0 everywhere. The corrected scores separate the approaches and hold up to scrutiny.", { x: MARGIN, y: 5.75, w: W - 2 * MARGIN, h: 0.45, fontSize: 14, italic: true, color: C.accent6 });
  s.addNotes("These fixes are encoded in the eval-runner rules and the harness code so they cannot regress.");

  // 11. Risks
  pres.addSection({ title: "Risks & recommendations" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Risks & recommendations" });
  s.addText("Key risks: the source is dated and the sample is small", { placeholder: "title" });
  const risks = [
    [fa.FaCalendarXmark, "Outdated source", "19th edition (2011). It still lists drotrecogin alfa for sepsis, a drug withdrawn from the market in 2011.", "License a current edition before any pilot"],
    [fa.FaChartLine, "Small evaluation", "9 answerable questions. Differences are directional, not statistically significant.", "Expand to 50+ clinician-labeled questions"],
    [fa.FaScaleBalanced, "Judge leniency", "LLM judges can be generous; one run scored perfect groundedness everywhere.", "Audit a sample of answers by hand"],
    [fa.FaGavel, "Regulatory & licensing", "Clinical decision support may be regulated; the manual's license bars redistribution; no patient data handling yet.", "Compliance review before clinical use"],
  ];
  for (const [i, [Icon, head, body, fix]] of risks.entries()) {
    const x = MARGIN + (i % 2) * (cw + 0.3);
    const y = 1.5 + Math.floor(i / 2) * (2.55 + 0.25);
    card(s, x, y, cw, 2.55, `risk-${i}`);
    await iconCircle(s, Icon, x + 0.3, y + 0.3, 0.65, C.accent3, `risk-${i}`);
    text(s, head, { x: x + 1.15, y: y + 0.3, w: cw - 1.45, h: 0.45, fontSize: 18, bold: true, color: C.text1, fontFace: THEME.headFontFace });
    text(s, body, { x: x + 1.15, y: y + 0.8, w: cw - 1.45, h: 0.95, fontSize: 14, color: C.text1 });
    text(s, [{ text: "Mitigation: ", options: { bold: true } }, { text: fix }], { x: x + 1.15, y: y + 1.8, w: cw - 1.45, h: 0.6, fontSize: 14, color: C.accent1 });
  }
  s.addNotes("RAG faithfully reproduces its source, including outdated guidance. The content source, not the model, is now the main quality bottleneck.");

  // 12. Business case
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Risks & recommendations" });
  s.addText("Running cost is negligible; the value is time and trust", { placeholder: "title" });
  const bw = 3.85;
  statCard(s, MARGIN, 1.6, bw, 1.95, `$${COST_PER_QUESTION.toFixed(4)}`, "estimated model cost per question", "biz-cost");
  statCard(s, MARGIN + bw + 0.3, 1.6, bw, 1.95, `≈ $${(COST_PER_QUESTION * 1000).toFixed(2)}`, "per 1,000 questions", "biz-1000");
  statCard(s, MARGIN + 2 * (bw + 0.3), 1.6, bw, 1.95, `${RAG.mean_latency_s} s`, "average time to a cited answer", "biz-latency");
  text(s, "Value to validate in a pilot", { x: MARGIN, y: 4.0, w: 8, h: 0.45, fontSize: 20, bold: true, color: C.text1, fontFace: THEME.headFontFace });
  const values = [
    [fa.FaStopwatch, "Time saved per lookup", "Measure minutes from question to verified answer vs searching the manual."],
    [fa.FaCircleCheck, "More verifiable answers", "Track the share of answers clinicians can verify vs a general chatbot."],
    [fa.FaUsers, "Standardized references", "Everyone works from the same source, supporting consistent care."],
  ];
  for (const [i, [Icon, head, body]] of values.entries()) {
    const x = MARGIN + i * (bw + 0.3);
    await iconCircle(s, Icon, x, 4.65, 0.65, C.accent1, `value-${i}`);
    text(s, head, { x: x + 0.8, y: 4.65, w: bw - 0.9, h: 0.45, fontSize: 16, bold: true, color: C.text1 });
    text(s, body, { x: x + 0.8, y: 5.15, w: bw - 0.9, h: 1.0, fontSize: 14, color: C.text1 });
  }
  s.addNotes("Cost estimated at OpenAI list prices for gpt-4o-mini with about 1,500 prompt and 600 output tokens per question; embeddings run locally for free; hosting excluded. Time savings are hypotheses to measure, not claims.");

  // 13. Recommendations
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Risks & recommendations" });
  s.addText("Next: pilot with a current source and clinician review", { placeholder: "title" });
  const phases = [
    ["30 days", "Fix the foundation", ["License a current reference and rebuild the index", "Grow the test set to 50+ questions with clinician-written answers"]],
    ["60 days", "Improve retrieval", ["Add keyword + vector hybrid search with a re-ranker", "Monitor quality, latency and cost per answer"]],
    ["90 days", "Limited pilot", ["Small clinician pilot measuring time-to-answer and satisfaction", "Complete compliance review (HIPAA, FDA guidance on decision-support software)"]],
  ];
  const tw = 3.85;
  s.addShape(pres.shapes.LINE, { x: MARGIN + 0.45, y: 2.15, w: 2 * (tw + 0.3), h: 0, line: { color: C.accent2, width: 2 }, objectName: "timeline" });
  phases.forEach(([when, head, items], i) => {
    const x = MARGIN + i * (tw + 0.3);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: 1.9, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { color: C.background1, width: 3 }, objectName: `phase-dot-${i}` });
    text(s, when, { x: x + 0.2, y: 1.4, w: 2.5, h: 0.4, fontSize: 16, bold: true, color: C.accent1, valign: "middle" });
    card(s, x, 2.7, tw, 3.3, `phase-${i}`);
    text(s, head, { x: x + 0.3, y: 2.95, w: tw - 0.6, h: 0.5, fontSize: 20, bold: true, color: C.text1, fontFace: THEME.headFontFace });
    text(s, bullets(items, 15), { x: x + 0.3, y: 3.6, w: tw - 0.6, h: 2.3 });
  });
  s.addNotes("The prototype proves feasibility and the evaluation method. The next investment is content currency and clinician-validated measurement, not a bigger model.");

  // 14. Closing
  pres.addSection({ title: "Closing" });
  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Closing" });
  s.addText("Thank you", { placeholder: "title" });
  s.addText(`Code, evaluation and decisions: ${REPO_URL}`, { placeholder: "body" });
  text(s, "React · FastAPI · Chroma · OpenAI · Docker · GitHub Actions", { x: MARGIN + 0.2, y: 6.4, w: 11, h: 0.4, fontSize: 14, color: C.accent2 });
  await iconCircle(s, fa.FaGithub, MARGIN + 0.2, 1.0, 0.95, C.accent1, "closing-icon");
  s.addNotes("Not medical advice: this is an educational portfolio project.");

  await pres.writeFile({ fileName: OUT });
  if (SKILL_SCRIPTS) {
    const { applyTheme } = require(path.join(SKILL_SCRIPTS, "apply_theme.js"));
    await applyTheme(OUT, THEME);
  } else {
    console.warn("PPTX_SKILL_SCRIPTS not set: theme colors not applied");
  }
  console.log(`Wrote ${OUT}`);
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
