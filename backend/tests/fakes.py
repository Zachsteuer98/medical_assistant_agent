"""Test doubles: no network, no vector DB."""

from app.corpora import CorpusSpec
from app.rag.llm import LLMError
from app.rag.store import Chunk

TEST_CORPUS = CorpusSpec(
    name="test",
    display_name="Test Manual",
    pdf_path=None,
    first_content_page=0,  # type: ignore[arg-type]
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
