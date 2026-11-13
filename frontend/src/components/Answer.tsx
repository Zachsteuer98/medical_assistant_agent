import Markdown from "react-markdown";
import type { AskResponse } from "../api/types";
import { citationRefFromHref, linkifyCitations, resolveCitationRef, sourceKey } from "../citations";
import type { CorpusGuide } from "../corpusGuides";

interface Props {
  response: AskResponse;
  guide: CorpusGuide;
  /** Called with the sourceKey of the card a chip points to. */
  onCite: (key: string) => void;
}

export function Answer({ response, guide, onCite }: Props) {
  if (!response.answered_from_context) {
    return (
      <div className="notice" role="note">
        <strong>{guide.notFoundTitle}</strong> {guide.notFoundBody}
      </div>
    );
  }
  return (
    <div className="answer">
      <Markdown
        components={{
          a: ({ href, children }) => {
            const ref = citationRefFromHref(href);
            if (ref === null) return <span>{children}</span>; // no external links from model output
            const target = resolveCitationRef(ref, response.citations);
            if (!target) {
              // The model cited something that wasn't retrieved; show it, but don't pretend it links.
              return <span className="cite-chip unresolved">{children}</span>;
            }
            const multiDocument = target.document !== target.source;
            const name = multiDocument ? `${target.citation_label}, ` : "";
            return (
              <button
                type="button"
                className="cite-chip"
                onClick={() => onCite(sourceKey(target.document, target.page))}
                aria-label={`Show source ${name}page ${target.page}`}
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
