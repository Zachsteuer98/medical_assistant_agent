import { describe, expect, it } from "vitest";
import type { Citation } from "./api/types";
import {
  citationRefFromHref,
  groupBySource,
  linkifyCitations,
  resolveCitationRef,
  sourceKey,
} from "./citations";

const DM = "VA/DoD Clinical Practice Guideline for the Management of Type 2 Diabetes Mellitus (2023)";
const HTN = "VA/DoD Clinical Practice Guideline for Diagnosis and Treatment of Hypertension in Primary Care (2026)";

function cite(document: string, citation_label: string, page: number, snippet = "s", cited = false): Citation {
  return { source: "VA/DoD Clinical Practice Guidelines", document, citation_label, page, snippet, cited };
}

/** Round-trip: every chip link in the linkified text parses back to these refs. */
function refsIn(markdown: string) {
  return [...markdown.matchAll(/\]\(([^)]+)\)/g)].map((m) => citationRefFromHref(m[1]));
}

describe("linkifyCitations", () => {
  it("converts legacy single and multi-page markers into page chips", () => {
    const out = linkifyCitations("A [Source Page: 12]. B [Source Pages: 3, 4]");
    expect(out).toBe("A [p. 12](#source/12). B [p. 3](#source/3) [p. 4](#source/4)");
    expect(refsIn(out)).toEqual([
      { label: null, page: 12 },
      { label: null, page: 3 },
      { label: null, page: 4 },
    ]);
  });

  it("converts a multi-document single-page marker with a spaced label", () => {
    const out = linkifyCitations("Metformin first [Source: Type 2 Diabetes CPG 2023, Page: 31].");
    expect(out).toBe("Metformin first [Type 2 Diabetes CPG 2023, p. 31](#source/Type%202%20Diabetes%20CPG%202023/31).");
    expect(refsIn(out)).toEqual([{ label: "Type 2 Diabetes CPG 2023", page: 31 }]);
  });

  it("converts a multi-document multi-page marker, naming the document on the first chip only", () => {
    const out = linkifyCitations("Target <130 [Source: Hypertension CPG 2026, Pages: 12, 14].");
    expect(out).toBe(
      "Target <130 [Hypertension CPG 2026, p. 12](#source/Hypertension%20CPG%202026/12) " +
        "[p. 14](#source/Hypertension%20CPG%202026/14).",
    );
    expect(refsIn(out)).toEqual([
      { label: "Hypertension CPG 2026", page: 12 },
      { label: "Hypertension CPG 2026", page: 14 },
    ]);
  });

  it("tolerates extra whitespace and handles both formats in one answer", () => {
    const out = linkifyCitations("x [Source:  Asthma CPG 2025 ,  Page: 7] y [Source Page: 2]");
    expect(refsIn(out)).toEqual([
      { label: "Asthma CPG 2025", page: 7 },
      { label: null, page: 2 },
    ]);
  });

  it("escapes markdown and parentheses in labels so the link stays intact", () => {
    const out = linkifyCitations("[Source: Low_Back (Pain) CPG, Page: 5]");
    expect(out).toBe("[Low\\_Back (Pain) CPG, p. 5](#source/Low_Back%20%28Pain%29%20CPG/5)");
    expect(refsIn(out)).toEqual([{ label: "Low_Back (Pain) CPG", page: 5 }]);
  });

  it("leaves text without markers untouched", () => {
    expect(linkifyCitations("No citations here [Source: , Page: x].")).toBe("No citations here [Source: , Page: x].");
  });
});

describe("citationRefFromHref", () => {
  it("accepts only citation links", () => {
    expect(citationRefFromHref("#source/175")).toEqual({ label: null, page: 175 });
    expect(citationRefFromHref("#source/COPD%20CPG%202021/9")).toEqual({ label: "COPD CPG 2021", page: 9 });
    expect(citationRefFromHref("https://evil.example")).toBeNull();
    expect(citationRefFromHref("#source/abc")).toBeNull();
    expect(citationRefFromHref("#source/%E0%A4%A/3")).toBeNull();
    expect(citationRefFromHref(undefined)).toBeNull();
  });
});

describe("resolveCitationRef", () => {
  const citations = [cite(DM, "Type 2 Diabetes CPG 2023", 12), cite(HTN, "Hypertension CPG 2026", 12)];

  it("matches by label (case and whitespace insensitive) and page", () => {
    expect(resolveCitationRef({ label: "hypertension  cpg 2026", page: 12 }, citations)?.document).toBe(HTN);
    expect(resolveCitationRef({ label: "Hypertension CPG 2026", page: 13 }, citations)).toBeUndefined();
    expect(resolveCitationRef({ label: "Unknown CPG", page: 12 }, citations)).toBeUndefined();
  });

  it("resolves page-only markers only when the page is unambiguous", () => {
    expect(resolveCitationRef({ label: null, page: 12 }, citations)).toBeUndefined();
    const merck = [{ source: "M", document: "M", citation_label: "M", page: 12, snippet: "a", cited: true }];
    expect(resolveCitationRef({ label: null, page: 12 }, merck)?.page).toBe(12);
  });
});

describe("groupBySource", () => {
  it("groups by (document, page) so equal page numbers in different documents stay separate", () => {
    const groups = groupBySource([
      cite(DM, "Type 2 Diabetes CPG 2023", 12, "a"),
      cite(HTN, "Hypertension CPG 2026", 12, "b", true),
      cite(DM, "Type 2 Diabetes CPG 2023", 12, "c"),
      cite(DM, "Type 2 Diabetes CPG 2023", 30, "d"),
    ]);
    expect(groups.map((g) => [g.document, g.page, g.cited, g.snippets])).toEqual([
      [HTN, 12, true, ["b"]],
      [DM, 12, false, ["a", "c"]],
      [DM, 30, false, ["d"]],
    ]);
    expect(groups[0]!.key).toBe(sourceKey(HTN, 12));
    expect(groups[0]!.label).toBe("Hypertension CPG 2026");
  });

  it("still merges chunks of the same page for single-document corpora", () => {
    const m = (page: number, snippet: string, cited = false) => ({
      source: "M",
      document: "M",
      citation_label: "M",
      page,
      snippet,
      cited,
    });
    const groups = groupBySource([m(1, "a"), m(2, "b", true), m(1, "c")]);
    expect(groups.map((g) => [g.page, g.cited, g.snippets])).toEqual([
      [2, true, ["b"]],
      [1, false, ["a", "c"]],
    ]);
  });
});
