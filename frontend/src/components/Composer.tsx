import { useState, type FormEvent, type KeyboardEvent } from "react";
import { QUESTION_MAX_CHARS, QUESTION_MIN_CHARS } from "../api/types";

interface Props {
  busy: boolean;
  onSubmit: (question: string) => void;
}

export function Composer({ busy, onSubmit }: Props) {
  const [text, setText] = useState("");
  const canSend = !busy && text.trim().length >= QUESTION_MIN_CHARS;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSubmit(text.trim());
    setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) submit(event);
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question" className="visually-hidden">
        Ask a clinical question
      </label>
      <textarea
        id="question"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        maxLength={QUESTION_MAX_CHARS}
        rows={2}
        placeholder="Ask a clinical question, e.g. first-line treatment for rheumatoid arthritis"
        aria-describedby="question-hint"
      />
      <div className="composer-row">
        <span id="question-hint" className="muted small">
          Enter to send · Shift+Enter for a new line · {text.length}/{QUESTION_MAX_CHARS}
        </span>
        <button type="submit" className="primary" disabled={!canSend}>
          {busy ? "Answering…" : "Ask"}
        </button>
      </div>
    </form>
  );
}
