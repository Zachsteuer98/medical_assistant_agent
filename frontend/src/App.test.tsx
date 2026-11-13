import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { AskResponse } from "./api/types";
import { PUBLIC_TOPICS } from "./corpusGuides";

const MERCK_NAME = "The Merck Manual of Diagnosis & Therapy, 19th ed.";
const merck = { source: MERCK_NAME, document: MERCK_NAME, citation_label: MERCK_NAME };

const ANSWER: AskResponse = {
  answer: "### Treatment\n- Anticoagulants [Source Page: 2595].",
  citations: [
    { ...merck, page: 2595, snippet: "Anticoagulation is the mainstay", cited: true },
    { ...merck, page: 2017, snippet: "Unrelated passage", cited: false },
  ],
  corpus: "merck",
  answered_from_context: true,
  disclaimer: "Not medical advice.",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockApi(askResponses: Response[], corpus = "merck") {
  const fetchMock = vi.fn<typeof fetch>((input) => {
    if (String(input).endsWith("/api/health")) {
      return Promise.resolve(jsonResponse({ status: "ok", corpus, indexed_chunks: 1 }));
    }
    const next = askResponses.shift();
    return next ? Promise.resolve(next) : Promise.reject(new TypeError("network"));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("shows Merck example questions in the empty state", async () => {
    mockApi([]);
    render(<App />);
    expect(await screen.findByRole("heading", { name: /ask the medical manual/i })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: /example questions/i })).getAllByRole("button")).toHaveLength(4);
  });

  it("asks a question and shows the answer with clickable citations and sources", async () => {
    const fetchMock = mockApi([jsonResponse(ANSWER)]);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(/ask a clinical question/i), "PE treatment?{Enter}");

    const chip = await screen.findByRole("button", { name: /show source page 2595/i });
    expect(screen.getByText(/anticoagulants/i)).toBeInTheDocument();
    const sources = screen.getByRole("complementary", { name: /sources/i });
    expect(within(sources).getByText("Page 2595")).toBeInTheDocument();
    expect(within(sources).getByText("Cited")).toBeInTheDocument();

    await user.click(chip);
    expect(within(sources).getByText("Page 2595").closest("li")).toHaveAttribute("aria-current", "true");

    const askCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/ask"));
    expect(JSON.parse(String(askCall?.[1]?.body))).toEqual({ question: "PE treatment?" });
  });

  it("shows a friendly error and recovers on retry", async () => {
    mockApi([jsonResponse({ detail: "x" }, 502), jsonResponse(ANSWER)]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /pulmonary embolism/i }));
    expect(await screen.findByText(/language model is temporarily unavailable/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByRole("button", { name: /show source page 2595/i })).toBeInTheDocument();
  });

  it("shows a not-found notice when the manual lacks the answer", async () => {
    mockApi([jsonResponse({ ...ANSWER, answered_from_context: false, citations: [] })]);
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText(/ask a clinical question/i), "COVID vaccine dosing?{Enter}");
    expect(await screen.findByText(/not found in the manual/i)).toBeInTheDocument();
  });

  it("keeps the disclaimer and shows a neutral empty state while the corpus is loading", () => {
    mockApi([]);
    render(<App />);
    expect(screen.getByRole("note")).toHaveTextContent(/not medical advice/i);
    expect(screen.getByText(/loading available topics/i)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /example questions/i })).not.toBeInTheDocument();
  });

  it("disables sending for blank input", () => {
    mockApi([]);
    render(<App />);
    expect(screen.getByRole("button", { name: /^ask$/i })).toBeDisabled();
  });

  it("warns when the service is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("network"))));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/unreachable/i));
  });

  describe("public corpus", () => {
    const DM = "VA/DoD Clinical Practice Guideline for the Management of Type 2 Diabetes Mellitus (2023)";
    const HTN = "VA/DoD Clinical Practice Guideline for Diagnosis and Treatment of Hypertension in Primary Care (2026)";
    const source = "VA/DoD Clinical Practice Guidelines";
    const PUBLIC_ANSWER: AskResponse = {
      answer: "- Target BP <130/80 [Source: Hypertension CPG 2026, Pages: 12, 20].",
      citations: [
        { source, document: DM, citation_label: "Type 2 Diabetes CPG 2023", page: 12, snippet: "Diabetes page 12", cited: false },
        { source, document: HTN, citation_label: "Hypertension CPG 2026", page: 12, snippet: "BP target text", cited: true },
        { source, document: HTN, citation_label: "Hypertension CPG 2026", page: 20, snippet: "More BP text", cited: true },
      ],
      corpus: "public",
      answered_from_context: true,
      disclaimer: "Not medical advice.",
    };

    it("lists covered topics, example questions and the scope note", async () => {
      mockApi([], "public");
      render(<App />);
      expect(await screen.findByRole("heading", { name: /ask the va\/dod guidelines/i })).toBeInTheDocument();
      const topics = within(screen.getByRole("list", { name: /covered topics/i })).getAllByRole("listitem");
      expect(topics.map((t) => t.textContent)).toEqual(PUBLIC_TOPICS);
      const examples = within(screen.getByRole("list", { name: /example questions/i })).getAllByRole("button");
      expect(examples.length).toBeGreaterThanOrEqual(4);
      expect(examples.length).toBeLessThanOrEqual(6);
      expect(screen.getByText(/answers come only from these 10 va\/dod/i)).toBeInTheDocument();
      expect(screen.getByRole("note")).toHaveTextContent(/not medical advice/i);
    });

    it("submits an example question and links chips to the matching (document, page) card", async () => {
      const fetchMock = mockApi([jsonResponse(PUBLIC_ANSWER)], "public");
      const user = userEvent.setup();
      render(<App />);

      const example = await screen.findByRole("button", { name: /blood pressure target/i });
      await user.click(example);

      const askCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/ask"));
      expect(JSON.parse(String(askCall?.[1]?.body))).toEqual({
        question: "What blood pressure target is recommended for adults with hypertension?",
      });
      expect(screen.getByLabelText(/ask a clinical question/i)).toHaveFocus();

      const chip = await screen.findByRole("button", { name: "Show source Hypertension CPG 2026, page 12" });
      expect(chip).toHaveTextContent("Hypertension CPG 2026, p. 12");
      expect(screen.getByRole("button", { name: "Show source Hypertension CPG 2026, page 20" })).toHaveTextContent("p. 20");

      const sources = screen.getByRole("complementary", { name: /sources/i });
      expect(within(sources).getAllByText("Page 12")).toHaveLength(2);

      chip.focus();
      await user.keyboard("{Enter}");
      const active = within(sources).getByText(HTN, { selector: ".source-card[aria-current] *" });
      expect(active.closest("li")).toHaveTextContent("BP target text");
      expect(active.closest("li")).toHaveFocus();
      expect(within(sources).getByText(DM).closest("li")).not.toHaveAttribute("aria-current");
    });

    it("uses guideline wording when the answer is not in the sources", async () => {
      mockApi([jsonResponse({ ...PUBLIC_ANSWER, answered_from_context: false, citations: [] })], "public");
      const user = userEvent.setup();
      render(<App />);
      await user.type(screen.getByLabelText(/ask a clinical question/i), "COVID vaccine dosing?{Enter}");
      expect(await screen.findByText(/not found in the guidelines/i)).toBeInTheDocument();
    });
  });
});
