import { useEffect, useRef } from "react";
import type { Citation } from "../api/types";
import { groupByPage } from "../citations";

interface Props {
  citations: Citation[] | null;
  activePage: number | null;
}

export function SourcesPanel({ citations, activePage }: Props) {
  const activeRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
    activeRef.current?.focus();
  }, [activePage]);

  return (
    <aside className="sources" aria-labelledby="sources-heading">
      <h2 id="sources-heading">Sources</h2>
      {citations === null ? (
        <p className="muted">Sources for the selected answer appear here.</p>
      ) : citations.length === 0 ? (
        <p className="muted">No passages were retrieved for this question.</p>
      ) : (
        <ul className="source-list">
          {groupByPage(citations).map((group) => {
            const active = group.page === activePage;
            return (
              <li
                key={group.page}
                ref={active ? activeRef : undefined}
                tabIndex={-1}
                className={`source-card${active ? " active" : ""}`}
                aria-current={active ? "true" : undefined}
              >
                <div className="source-head">
                  <span className="source-page">Page {group.page}</span>
                  {group.cited && <span className="badge">Cited</span>}
                </div>
                <p className="source-name">{group.source}</p>
                {group.snippets.map((snippet, i) => (
                  <blockquote key={i}>{snippet}…</blockquote>
                ))}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
