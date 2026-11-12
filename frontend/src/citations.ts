import type { Citation } from "./api/types";

const SOURCE_MARKER = /\[Source Pages?:\s*([\d,\s]+)\]/g;
export const CITATION_HREF_PREFIX = "#source-";

/** Turn "[Source Page: 12]" markers into markdown links the UI renders as clickable chips. */
export function linkifyCitations(answer: string): string {
  return answer.replace(SOURCE_MARKER, (_match, pages: string) =>
    pages
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => `[p. ${p}](${CITATION_HREF_PREFIX}${p})`)
      .join(" "),
  );
}

export function pageFromHref(href: string | undefined): number | null {
  if (!href?.startsWith(CITATION_HREF_PREFIX)) return null;
  const page = Number(href.slice(CITATION_HREF_PREFIX.length));
  return Number.isInteger(page) ? page : null;
}

export interface SourceGroup {
  page: number;
  source: string;
  cited: boolean;
  snippets: string[];
}

/** One card per page, preserving retrieval order; cited pages first. */
export function groupByPage(citations: Citation[]): SourceGroup[] {
  const groups = new Map<number, SourceGroup>();
  for (const c of citations) {
    const group = groups.get(c.page);
    if (group) {
      group.snippets.push(c.snippet);
      group.cited ||= c.cited;
    } else {
      groups.set(c.page, { page: c.page, source: c.source, cited: c.cited, snippets: [c.snippet] });
    }
  }
  const all = [...groups.values()];
  return [...all.filter((g) => g.cited), ...all.filter((g) => !g.cited)];
}
