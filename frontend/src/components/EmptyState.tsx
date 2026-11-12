const EXAMPLE_QUESTIONS = [
  "What are the common symptoms and treatments for pulmonary embolism?",
  "What are the first-line options and alternatives for managing rheumatoid arthritis?",
  "What is the protocol for managing sepsis in a critical care unit?",
  "What are the diagnostic steps for suspected endocrine disorders?",
];

interface Props {
  onPick: (question: string) => void;
}

export function EmptyState({ onPick }: Props) {
  return (
    <div className="empty">
      <h2>Ask the medical manual</h2>
      <p className="muted">
        Answers come only from the reference manual, with every claim linked to its source page.
      </p>
      <ul className="examples" aria-label="Example questions">
        {EXAMPLE_QUESTIONS.map((q) => (
          <li key={q}>
            <button type="button" className="example" onClick={() => onPick(q)}>
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
