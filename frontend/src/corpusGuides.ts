/**
 * Visitor-facing copy per corpus (the `corpus` value from /api/health). Single source of truth for
 * covered topics and example questions; keep topics in sync with docs/adr/0004-public-demo-corpus.md.
 */

export interface CorpusGuide {
  subtitle: string;
  heading: string;
  /** Short note on where answers come from. */
  scopeNote: string;
  /** Covered topics; empty when the corpus is a general reference. */
  topics: readonly string[];
  examples: readonly string[];
  loadingText: string;
  notFoundTitle: string;
  notFoundBody: string;
  placeholder: string;
}

const MERCK_GUIDE: CorpusGuide = {
  subtitle: "RAG over The Merck Manual of Diagnosis & Therapy, 19th ed. (2011)",
  heading: "Ask the medical manual",
  scopeNote: "Answers come only from the reference manual, with every claim linked to its source page.",
  topics: [],
  examples: [
    "What are the common symptoms and treatments for pulmonary embolism?",
    "What are the first-line options and alternatives for managing rheumatoid arthritis?",
    "What is the protocol for managing sepsis in a critical care unit?",
    "What are the diagnostic steps for suspected endocrine disorders?",
  ],
  loadingText: "Searching the manual and drafting an answer…",
  notFoundTitle: "Not found in the manual.",
  notFoundBody:
    "The reference doesn't cover this question, so no answer was generated. Try rephrasing, or consult a current guideline.",
  placeholder: "Ask a clinical question, e.g. first-line treatment for rheumatoid arthritis",
};

export const PUBLIC_TOPICS = [
  "Type 2 diabetes",
  "Hypertension",
  "Lipids (dyslipidemia)",
  "Asthma",
  "COPD",
  "Chronic kidney disease (CKD)",
  "Depression (major depressive disorder)",
  "Low back pain",
  "Headache",
  "Insomnia and sleep apnea",
] as const;

const PUBLIC_GUIDE: CorpusGuide = {
  subtitle: "RAG over 10 VA/DoD Clinical Practice Guidelines",
  heading: "Ask the VA/DoD guidelines",
  scopeNote:
    "Answers come only from these 10 VA/DoD Clinical Practice Guidelines, with every claim linked to its guideline and page. Questions outside these topics will not be answered.",
  topics: PUBLIC_TOPICS,
  examples: [
    "What blood pressure target is recommended for adults with hypertension?",
    "What is first-line treatment for chronic insomnia?",
    "What medications are recommended for migraine prevention?",
    "How should COPD exacerbations be treated?",
    "When is a statin recommended for primary prevention of cardiovascular disease?",
    "What non-drug treatments are recommended for chronic low back pain?",
  ],
  loadingText: "Searching the guidelines and drafting an answer…",
  notFoundTitle: "Not found in the guidelines.",
  notFoundBody:
    "The covered VA/DoD guidelines don't address this question, so no answer was generated. Try rephrasing, or ask about one of the covered topics.",
  placeholder: "Ask a clinical question, e.g. first-line treatment for chronic insomnia",
};

/** Used while the corpus is unknown (health check pending or failed, or an unrecognised corpus). */
export const GENERIC_GUIDE: CorpusGuide = {
  subtitle: "Retrieval-augmented answers from clinical references",
  heading: "Ask a clinical question",
  scopeNote: "Answers come only from the indexed reference, with every claim linked to its source.",
  topics: [],
  examples: [],
  loadingText: "Searching the sources and drafting an answer…",
  notFoundTitle: "Not found in the sources.",
  notFoundBody:
    "The reference doesn't cover this question, so no answer was generated. Try rephrasing, or consult a current guideline.",
  placeholder: "Ask a clinical question",
};

const GUIDES: Readonly<Record<string, CorpusGuide>> = { merck: MERCK_GUIDE, public: PUBLIC_GUIDE };

export function guideFor(corpus: string | null): CorpusGuide {
  return (corpus !== null && Object.hasOwn(GUIDES, corpus) ? GUIDES[corpus] : undefined) ?? GENERIC_GUIDE;
}
