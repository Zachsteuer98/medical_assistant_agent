import type { AskResponse, HealthResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const REQUEST_TIMEOUT_MS = 60_000;

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  422: "Please enter a question between 3 and 1,000 characters.",
  429: "You're sending questions too quickly. Wait a minute and try again.",
  502: "The language model is temporarily unavailable. Please try again.",
  503: "The knowledge base isn't ready yet. Please try again shortly.",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "AbortError";
    throw new ApiError(
      timedOut
        ? "The request timed out. Please try again."
        : "Can't reach the server. Check your connection and try again.",
    );
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    throw new ApiError(
      STATUS_MESSAGES[response.status] ?? `Something went wrong (error ${response.status}).`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function askQuestion(question: string): Promise<AskResponse> {
  return request<AskResponse>("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}
