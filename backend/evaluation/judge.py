"""LLM-as-judge for the RAG triad. Judge model differs from the generator to avoid
self-preference bias, and always sees the real retrieved context."""

import json
from dataclasses import dataclass

from openai import OpenAI

MIN_SCORE, MAX_SCORE = 1, 5

_RUBRICS = {
    "context_relevance": (
        "Rate how much of the information needed to fully answer the QUESTION is present "
        "in the CONTEXT. 1 = none of it, 5 = everything needed. Ignore the ANSWER."
    ),
    "groundedness": (
        "Rate whether every claim in the ANSWER is supported by the CONTEXT. "
        "1 = mostly unsupported or fabricated, 5 = every claim supported. "
        "A refusal that says the context lacks the answer counts as fully grounded."
    ),
    "answer_relevance": (
        "Rate how completely and directly the ANSWER addresses all parts of the QUESTION. "
        "1 = irrelevant, 5 = complete and direct. Ignore whether it is grounded."
    ),
}
METRICS = tuple(_RUBRICS)

_SYSTEM = (
    "You are a strict clinical auditor evaluating a medical retrieval-augmented assistant. "
    "{rubric} Respond with JSON only: "
    '{{"score": <integer 1-5>, "rationale": "<one sentence>"}}'
)
_USER = "### QUESTION\n{question}\n\n### CONTEXT\n{context}\n\n### ANSWER\n{answer}"


class JudgeOutputError(ValueError):
    """The judge returned malformed or out-of-range output."""


@dataclass(frozen=True)
class Verdict:
    score: int
    rationale: str


def parse_verdict(raw: str) -> Verdict:
    try:
        data = json.loads(raw)
        score = int(data["score"])
        rationale = str(data["rationale"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise JudgeOutputError(f"Unparseable judge output: {raw[:200]!r}") from exc
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise JudgeOutputError(f"Score out of range: {score}")
    return Verdict(score, rationale)


class Judge:
    def __init__(self, client: OpenAI, model: str):
        self._client = client
        self._model = model

    def rate(self, metric: str, question: str, context: str, answer: str) -> Verdict:
        completion = self._client.chat.completions.create(
            model=self._model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM.format(rubric=_RUBRICS[metric])},
                {
                    "role": "user",
                    "content": _USER.format(question=question, context=context, answer=answer),
                },
            ],
        )
        return parse_verdict(completion.choices[0].message.content or "")
