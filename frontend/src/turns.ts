import type { AskResponse } from "./api/types";

/** A question and its lifecycle. A discriminated union makes impossible states unrepresentable. */
export type Turn =
  | { id: number; question: string; status: "loading" }
  | { id: number; question: string; status: "done"; response: AskResponse }
  | { id: number; question: string; status: "error"; error: string; retryable: boolean };
