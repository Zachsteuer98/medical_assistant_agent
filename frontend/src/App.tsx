import { useCallback, useEffect, useRef, useState } from "react";
import { askQuestion, getHealth } from "./api/client";
import { Answer } from "./components/Answer";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { SourcesPanel } from "./components/SourcesPanel";
import type { Turn } from "./turns";

type Health = "checking" | "ok" | "down";

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activePage, setActivePage] = useState<number | null>(null);
  const [health, setHealth] = useState<Health>("checking");
  const nextId = useRef(1);

  useEffect(() => {
    getHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("down"));
  }, []);

  const run = useCallback(async (id: number, question: string) => {
    try {
      const response = await askQuestion(question);
      setTurns((ts) => ts.map((t) => (t.id === id ? { id, question, status: "done", response } : t)));
      setSelectedId(id);
      setActivePage(null);
      setHealth("ok");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setTurns((ts) => ts.map((t) => (t.id === id ? { id, question, status: "error", error: message } : t)));
    }
  }, []);

  const ask = useCallback(
    (question: string) => {
      const id = nextId.current++;
      setTurns((ts) => [...ts, { id, question, status: "loading" }]);
      void run(id, question);
    },
    [run],
  );

  const retry = useCallback(
    (turn: Turn) => {
      setTurns((ts) => ts.map((t) => (t.id === turn.id ? { id: t.id, question: t.question, status: "loading" } : t)));
      void run(turn.id, turn.question);
    },
    [run],
  );

  const busy = turns.some((t) => t.status === "loading");
  const selected = turns.find((t) => t.id === selectedId);
  const citations = selected?.status === "done" ? selected.response.citations : null;

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Medical Assistant Agent</h1>
          <p className="muted small">RAG over The Merck Manual of Diagnosis &amp; Therapy, 19th ed. (2011)</p>
        </div>
      </header>
      <p className="disclaimer" role="note">
        <strong>Not medical advice.</strong> Educational decision-support only. Verify against
        current guidelines and clinical judgment.
      </p>
      {health === "down" && (
        <p className="banner-error" role="alert">
          The assistant service is unreachable. Answers won't load until it's back.
        </p>
      )}

      <main className="layout">
        <section className="chat" aria-label="Conversation">
          <div className="log" role="log" aria-live="polite" aria-busy={busy}>
            {turns.length === 0 && <EmptyState onPick={ask} />}
            {turns.map((turn) => (
              <article
                key={turn.id}
                className={`turn${turn.id === selectedId ? " selected" : ""}`}
                aria-label={`Question: ${turn.question}`}
              >
                <p className="question">{turn.question}</p>
                {turn.status === "loading" && (
                  <p className="loading">Searching the manual and drafting an answer…</p>
                )}
                {turn.status === "error" && (
                  <div className="error" role="alert">
                    <span>{turn.error}</span>
                    <button type="button" onClick={() => retry(turn)}>
                      Retry
                    </button>
                  </div>
                )}
                {turn.status === "done" && (
                  <>
                    <Answer
                      response={turn.response}
                      onCite={(page) => {
                        setSelectedId(turn.id);
                        setActivePage(page);
                      }}
                    />
                    {turn.id !== selectedId && turn.response.citations.length > 0 && (
                      <button type="button" className="link" onClick={() => setSelectedId(turn.id)}>
                        Show sources
                      </button>
                    )}
                  </>
                )}
              </article>
            ))}
          </div>
          <Composer busy={busy} onSubmit={ask} />
        </section>
        <SourcesPanel citations={citations} activePage={activePage} />
      </main>
    </div>
  );
}
