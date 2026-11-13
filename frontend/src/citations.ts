import type { Citation } from "./api/types";

/**
 * Answer markers, mirroring backend/app/rag/service.py:
 * - single-document (Merck): "[Source Page: 12]" / "[Source Pages: 3, 4]"
 * - multi-document:          "[Source: <label>, Page: 12]" / "[Source: <label>, Pages: 3, 4]"
 */
const SOURCE_MARKER =
  /\[Source(?: Pages?:\s*([\d,\s]+)|:\s*([^\],]+?)\s*,\s*Pages?:\s*([\d,\s]+))\]/g;
const CITATION_HREF_PREFIX = "#source/";
const MARKDOWN_SPECIAL = /[\\`*_<>]/g;

/** A citation as written by the model. `label` is null for page-only (single-document) markers. */
export interface CitationRef {
  label: string | null;
  page: number;
}

function splitPages(group: string): number[] {
  return group
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean)
    .map(Number);
}

function hrefFor({ label, page }: CitationRef): string {
  if (label === null) return `${CITATION_HREF_PREFIX}${page}`;
  // Parentheses would end a markdown link destination early.
  const encoded = encodeURIComponent(label).replace(/\(/g, "%28").replace(/\)/g, "%29");
  return `${CITATION_HREF_PREFIX}${encoded}/${page}`;
}

/** The label is shown on the first chip of a marker only, to keep multi-page citations compact. */
function chipText(ref: CitationRef, isFirst: boolean): string {
  const pageText = `p. ${ref.page}`;
  if (ref.label === null || !isFirst) return pageText;
  return `${ref.label.replace(MARKDOWN_SPECIAL, "\\$&")}, ${pageText}`;
}

/** Turn source markers into markdown links the UI renders as clickable chips. */
export function linkifyCitations(answer: string): string {
  return answer.replace(
    SOURCE_MARKER,
    (_match, legacyPages: string | undefined, label: string | undefined, labelPages: string | undefined) => {
      const docLabel = label === undefined ? null : label.trim();
      const pages = splitPages(legacyPages ?? labelPages ?? "");
      return pages
        .map((page, i) => {
          const ref = { label: docLabel, page };
          return `[${chipText(ref, i === 0)}](${hrefFor(ref)})`;
        })
        .join(" ");
    },
  );
}

/** Parse a chip href produced by linkifyCitations; null for anything else (e.g. model-written links). */
export function citationRefFromHref(href: string | undefined): CitationRef | null {
  if (!href?.startsWith(CITATION_HREF_PREFIX)) return null;
  const parts = href.slice(CITATION_HREF_PREFIX.length).split("/");
  if (parts.length < 1 || parts.length > 2) return null;
  const page = Number(parts[parts.length - 1]);
  if (!Number.isInteger(page) || page < 1) return null;
  if (parts.length === 1) return { label: null, page };
  try {
    return { label: decodeURIComponent(parts[0]!), page };
  } catch {
    return null; // malformed percent-encoding
  }
}

function normalize(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(" ").toLocaleLowerCase();
}

/** Stable identity of a source card: same page number in different documents must not merge. */
export function sourceKey(document: string, page: number): string {
  return JSON.stringify([document, page]);
}

/**
 * Find the retrieved passage a chip refers to. A page-only marker is resolved only when exactly
 * one document has that page, so a chip never highlights the wrong guideline.
 */
export function resolveCitationRef(ref: CitationRef, citations: Citation[]): Citation | undefined {
  const onPage = citations.filter((c) => c.page === ref.page);
  if (ref.label === null) {
    const documents = new Set(onPage.map((c) => c.document));
    return documents.size === 1 ? onPage[0] : undefined;
  }
  const wanted = normalize(ref.label);
  return onPage.find((c) => normalize(c.citation_label) === wanted || normalize(c.document) === wanted);
}

export interface SourceGroup {
  key: string;
  document: string;
  label: string;
  page: number;
  cited: boolean;
  snippets: string[];
}

/** One card per (document, page), preserving retrieval order; cited cards first. */
export function groupBySource(citations: Citation[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const c of citations) {
    const key = sourceKey(c.document, c.page);
    const group = groups.get(key);
    if (group) {
      group.snippets.push(c.snippet);
      group.cited ||= c.cited;
    } else {
      groups.set(key, {
        key,
        document: c.document,
        label: c.citation_label,
        page: c.page,
        cited: c.cited,
        snippets: [c.snippet],
      });
    }
  }
  const all = [...groups.values()];
  return [...all.filter((g) => g.cited), ...all.filter((g) => !g.cited)];
}
