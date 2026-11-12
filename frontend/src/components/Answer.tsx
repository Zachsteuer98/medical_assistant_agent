import Markdown from "react-markdown";
import type { AskResponse } from "../api/types";
import { linkifyCitations, pageFromHref } from "../citations";

interface Props {
  response: AskResponse;
  onCite: (page: number) => void;
}

export function Answer({ response, onCite }: Props) {
  if (!response.answered_from_context) {
    return (
      <div className="notice" role="note">
        <strong>Not found in the manual.</strong> The reference doesn't cover this question, so no
        answer was generated. Try rephrasing, or consult a current guideline.
      </div>
    );
  }
  return (
    <div className="answer">
      <Markdown
        components={{
          a: ({ href, children }) => {
            const page = pageFromHref(href);
            if (page === null) return <span>{children}</span>; // no external links from model output
            return (
              <button
                type="button"
                className="cite-chip"
                onClick={() => onCite(page)}
                aria-label={`Show source page ${page}`}
              >
                {children}
              </button>
            );
          },
        }}
      >
        {linkifyCitations(response.answer)}
      </Markdown>
    </div>
  );
}
