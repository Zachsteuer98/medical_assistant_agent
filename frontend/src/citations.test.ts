import { describe, expect, it } from "vitest";
import { groupByPage, linkifyCitations, pageFromHref } from "./citations";

describe("linkifyCitations", () => {
  it("converts single and multi-page markers into links", () => {
    expect(linkifyCitations("A [Source Page: 12]. B [Source Pages: 3, 4]")).toBe(
      "A [p. 12](#source-12). B [p. 3](#source-3) [p. 4](#source-4)",
    );
  });

  it("leaves text without markers untouched", () => {
    expect(linkifyCitations("No citations here.")).toBe("No citations here.");
  });
});

describe("pageFromHref", () => {
  it("extracts the page only from citation links", () => {
    expect(pageFromHref("#source-175")).toBe(175);
    expect(pageFromHref("https://evil.example")).toBeNull();
    expect(pageFromHref(undefined)).toBeNull();
  });
});

describe("groupByPage", () => {
  it("merges chunks from the same page and lists cited pages first", () => {
    const groups = groupByPage([
      { source: "M", page: 1, snippet: "a", cited: false },
      { source: "M", page: 2, snippet: "b", cited: true },
      { source: "M", page: 1, snippet: "c", cited: false },
    ]);
    expect(groups.map((g) => [g.page, g.cited, g.snippets])).toEqual([
      [2, true, ["b"]],
      [1, false, ["a", "c"]],
    ]);
  });
});
