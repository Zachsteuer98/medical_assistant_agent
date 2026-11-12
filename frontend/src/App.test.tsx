import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { AskResponse } from "./api/types";

const ANSWER: AskResponse = {
  answer: "### Treatment\n- Anticoagulants [Source Page: 2595].",
  citations: [
    { source: "Merck Manual", page: 2595, snippet: "Anticoagulation is the mainstay", cited: true },
    { source: "Merck Manual", page: 2017, snippet: "Unrelated passage", cited: false },
  ],
  corpus: "merck",
  answered_from_context: true,
  disclaimer: "Not medical advice.",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockApi(askResponses: Response[]) {
  const fetchMock = vi.fn<typeof fetch>((input) => {
    if (String(input).endsWith("/api/health")) {
      return Promise.resolve(jsonResponse({ status: "ok", corpus: "merck", indexed_chunks: 1 }));
    }
    const next = askResponses.shift();
    return next ? Promise.resolve(next) : Promise.reject(new TypeError("network"));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("shows example questions in the empty state", () => {
    mockApi([]);
    render(<App />);
    expect(screen.getByRole("heading", { name: /ask the medical manual/i })).toBeInTheDocument();
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

    await user.click(screen.getAllByRole("button", { name: /pulmonary embolism/i })[0]!);
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
});
