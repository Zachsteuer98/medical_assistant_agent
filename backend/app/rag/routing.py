"""Document routing for multi-document corpora: pick the guideline(s) a question is about.

Without routing, MMR over the whole corpus lets a near-topic chunk from another guideline
(e.g. COPD text for an asthma question) take a context slot and import conflicting advice.
Routing scores each document by the summed similarity of its chunks among the top candidates,
then restricts retrieval to the best document, plus the runner-up when it scores close enough
(questions such as CKD + diabetes legitimately span two guidelines).
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

# Runner-up document is kept when its score is at least this fraction of the top score.
# Observed on the public eval set: true two-guideline questions score ~0.97 of the top
# (CKD/diabetes, CKD/hypertension), cross-guideline leakage at most ~0.32 (COPD for an
# asthma question). 0.5 sits well inside that gap.
DEFAULT_SECOND_DOCUMENT_RATIO = 0.5
# Candidates scored for routing (the same pool size MMR uses at k=5).
DEFAULT_ROUTING_CANDIDATES = 20
MAX_ROUTED_DOCUMENTS = 2


@dataclass(frozen=True)
class RoutingConfig:
    candidates: int = DEFAULT_ROUTING_CANDIDATES
    second_document_ratio: float = DEFAULT_SECOND_DOCUMENT_RATIO

    def __post_init__(self) -> None:
        if self.candidates < 1:
            raise ValueError("routing candidates must be >= 1")
        if not 0.0 < self.second_document_ratio <= 1.0:
            raise ValueError("second_document_ratio must be in (0, 1]")


def document_scores(sources: Sequence[str], similarities: Sequence[float]) -> dict[str, float]:
    """Summed similarity per document over the given candidate chunks."""
    if len(sources) != len(similarities):
        raise ValueError("sources and similarities must have the same length")
    scores: dict[str, float] = defaultdict(float)
    for source, similarity in zip(sources, similarities, strict=True):
        scores[source] += similarity
    return dict(scores)


def route_documents(
    sources: Sequence[str], similarities: Sequence[float], second_document_ratio: float
) -> list[str]:
    """Documents to retrieve from, best first. Empty input gives an empty list.

    Ties are broken by document name so the result never depends on candidate order.
    """
    scores = document_scores(sources, similarities)
    ranked = sorted(scores, key=lambda source: (-scores[source], source))
    if len(ranked) < MAX_ROUTED_DOCUMENTS:
        return ranked
    top, runner_up = ranked[0], ranked[1]
    if scores[top] > 0 and scores[runner_up] >= second_document_ratio * scores[top]:
        return [top, runner_up]
    return [top]
