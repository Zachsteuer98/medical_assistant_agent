import type { CorpusGuide } from "../corpusGuides";

interface Props {
  guide: CorpusGuide;
  /** True while the health check that identifies the corpus is still pending. */
  loading: boolean;
  onPick: (question: string) => void;
}

export function EmptyState({ guide, loading, onPick }: Props) {
  return (
    <div className="empty">
      <h2>{guide.heading}</h2>
      <p className="muted">{guide.scopeNote}</p>
      {loading && <p className="muted small">Loading available topics…</p>}
      {guide.topics.length > 0 && (
        <>
          <h3 id="topics-heading" className="empty-subheading">
            Covered topics
          </h3>
          <ul className="topics" aria-labelledby="topics-heading">
            {guide.topics.map((topic) => (
              <li key={topic}>{topic}</li>
            ))}
          </ul>
        </>
      )}
      {guide.examples.length > 0 && (
        <>
          <h3 id="examples-heading" className="empty-subheading">
            Try an example
          </h3>
          <ul className="examples" aria-label="Example questions">
            {guide.examples.map((q) => (
              <li key={q}>
                <button type="button" className="example" onClick={() => onPick(q)}>
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
