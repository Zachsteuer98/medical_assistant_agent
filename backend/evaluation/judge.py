"""LLM-as-judge: the RAG triad (scored against the real retrieved context) and answer
correctness (scored against reference facts, without the context). The judge model differs
from the generator to avoid self-preference bias."""

import json
from dataclasses import dataclass
from typing import Literal

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


# --- Answer correctness against reference facts ------------------------------------------
# Scored without the retrieved context: a confident answer built from the wrong chunk is
# "grounded" but still wrong, which the triad above cannot detect.

FactLabel = Literal["yes", "partly", "no"]
_FACT_WEIGHTS: dict[str, float] = {"yes": 1.0, "partly": 0.5, "no": 0.0}
Grade = Literal["pass", "partial", "fail"]
# Numeric form of the grade, on the triad's 1-5 scale so it can share tables and charts.
GRADE_SCORES: dict[str, int] = {"pass": 5, "partial": 3, "fail": 1}

_CORRECTNESS_SYSTEM = """\
You are a strict clinical auditor. You compare an ANSWER from a clinical assistant with \
REFERENCE FACTS taken from the {source}. You do not see the assistant's source text; judge \
only against the reference facts and the question.

1. COVERAGE. For each reference fact, in order, label how fully the ANSWER states it:
   "yes" = every essential element (drug, threshold, population, direction) is present.
   Equivalent wording counts. Naming a drug class counts as stating every listed drug that
   belongs to that class by standard pharmacological classification (e.g. "orexin receptor
   antagonists" covers daridorexant, lemborexant and suvorexant).
   "partly" = some essential elements are present but others are missing.
   "no" = absent.
2. CONTRADICTION. Set "contradiction" to true only if the ANSWER makes an explicit statement
   that would make a clinician act differently from a reference fact:
   - it recommends a different drug, regimen, target or population than a reference fact for
     the same situation (e.g. a different first-line therapy), or reverses a recommendation's
     direction (for vs. against); or
   - it applies advice for a different disease (e.g. cited to another condition's guideline)
     to this question's condition, and that advice conflicts with a reference fact.
   Missing information is NEVER a contradiction; it is already captured by COVERAGE. Extra
   details that do not conflict, recommendation-strength wording, and content cited to another
   guideline that agrees with the reference facts are not contradictions either.
   If contradiction is true, "contradiction_detail" must quote the conflicting sentence from
   the ANSWER verbatim. If you cannot quote such a sentence, contradiction is false.
Respond with JSON only:
{{"facts": [<one of "yes" | "partly" | "no" per reference fact, in order>],
"contradiction": <true | false>,
"contradiction_detail": "<verbatim quote from the ANSWER, or empty>",
"rationale": "<one sentence>"}}"""
_CORRECTNESS_USER = (
    "### QUESTION\n{question}\n\n### REFERENCE FACTS\n{facts}\n\n### ANSWER\n{answer}"
)


@dataclass(frozen=True)
class CorrectnessVerdict:
    fact_labels: tuple[str, ...]
    contradiction: bool
    contradiction_detail: str
    rationale: str

    @property
    def coverage(self) -> float:
        """Fraction of reference facts covered; "partly" counts half."""
        return sum(_FACT_WEIGHTS[label] for label in self.fact_labels) / len(self.fact_labels)

    @property
    def grade(self) -> Grade:
        # A contradiction can mislead even when every fact is also present, so it always fails.
        if self.contradiction or self.coverage == 0:
            return "fail"
        return "pass" if self.coverage == 1 else "partial"

    @property
    def score(self) -> int:
        return GRADE_SCORES[self.grade]


def parse_correctness(raw: str, n_facts: int) -> CorrectnessVerdict:
    try:
        data = json.loads(raw)
        labels = tuple(data["facts"])
        contradiction = data["contradiction"]
        detail = str(data.get("contradiction_detail", ""))
        rationale = str(data["rationale"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise JudgeOutputError(f"Unparseable correctness output: {raw[:200]!r}") from exc
    if len(labels) != n_facts or any(label not in _FACT_WEIGHTS for label in labels):
        raise JudgeOutputError(f"Expected {n_facts} labels from {sorted(_FACT_WEIGHTS)}: {labels}")
    if not isinstance(contradiction, bool):
        raise JudgeOutputError(f"contradiction must be a JSON boolean, got {contradiction!r}")
    return CorrectnessVerdict(labels, contradiction, detail, rationale)


def format_facts(facts: tuple[str, ...]) -> str:
    return "\n".join(f"{i}. {fact}" for i, fact in enumerate(facts, 1))


class Judge:
    def __init__(self, client: OpenAI, model: str):
        self._client = client
        self._model = model

    def rate(self, metric: str, question: str, context: str, answer: str) -> Verdict:
        user = _USER.format(question=question, context=context, answer=answer)
        return parse_verdict(self._complete(_SYSTEM.format(rubric=_RUBRICS[metric]), user))

    def grade_correctness(
        self, question: str, source: str, facts: tuple[str, ...], answer: str
    ) -> CorrectnessVerdict:
        if not facts:
            raise ValueError("Correctness needs at least one reference fact")
        user = _CORRECTNESS_USER.format(question=question, facts=format_facts(facts), answer=answer)
        system = _CORRECTNESS_SYSTEM.format(source=source)
        return parse_correctness(self._complete(system, user), len(facts))

    def _complete(self, system: str, user: str) -> str:
        completion = self._client.chat.completions.create(
            model=self._model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return completion.choices[0].message.content or ""
