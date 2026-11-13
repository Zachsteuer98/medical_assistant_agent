"""Test doubles: no network, no vector DB."""

from pathlib import Path

from app.corpora import CorpusDocument, CorpusSpec
from app.rag.llm import LLMError
from app.rag.store import Chunk

TEST_CORPUS = CorpusSpec(
    name="test",
    display_name="Test Manual",
    documents=(CorpusDocument("Test Manual", Path("unused.pdf"), first_content_page=0),),
)

MULTI_CORPUS = CorpusSpec(
    name="multi",
    display_name="Test Guidelines",
    documents=(
        CorpusDocument(
            "Guideline for Diabetes (2023)", Path("unused-a.pdf"), 0, citation_label="Diabetes"
        ),
        CorpusDocument(
            "Guideline for Hypertension (2026)", Path("unused-b.pdf"), 0, citation_label="HTN"
        ),
    ),
)


class FakeRetriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks

    def retrieve(self, question: str, k: int) -> list[Chunk]:
        return self.chunks[:k]

    def count(self) -> int:
        return len(self.chunks)


class FakeLLM:
    def __init__(self, answer: str = "", fail: bool = False):
        self.answer = answer
        self.fail = fail
        self.last_user: str | None = None

    def complete(self, system: str, user: str) -> str:
        if self.fail:
            raise LLMError("boom")
        self.last_user = user
        return self.answer
