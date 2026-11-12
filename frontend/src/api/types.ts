// Mirrors backend/app/schemas.py. Keep in sync.

export interface Citation {
  source: string;
  /** 1-based PDF page number */
  page: number;
  snippet: string;
  /** True if the answer explicitly cites this page */
  cited: boolean;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  corpus: string;
  answered_from_context: boolean;
  disclaimer: string;
}

export interface HealthResponse {
  status: string;
  corpus: string;
  indexed_chunks: number;
}

export const QUESTION_MIN_CHARS = 3;
export const QUESTION_MAX_CHARS = 1000;
