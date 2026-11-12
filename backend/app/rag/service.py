"""Answer a question: retrieve -> prompt -> generate -> attach citations."""

import re

from app.corpora import CorpusSpec
from app.rag.llm import ChatModel
from app.rag.prompts import FALLBACK_ANSWER, SYSTEM_PROMPT, USER_TEMPLATE, format_context
from app.rag.store import Chunk, Retriever
from app.schemas import AskResponse, Citation

SNIPPET_CHARS = 300
_CITED_PAGES = re.compile(r"\[Source Pages?:\s*([\d,\s]+)\]")


def cited_pages(answer: str) -> set[int]:
    return {int(p) for group in _CITED_PAGES.findall(answer) for p in group.split(",") if p.strip()}


class AssistantService:
    def __init__(self, retriever: Retriever, llm: ChatModel, corpus: CorpusSpec, top_k: int):
        self._retriever = retriever
        self._llm = llm
        self._corpus = corpus
        self._top_k = top_k

    def indexed_chunks(self) -> int:
        return self._retriever.count()

    @property
    def corpus_name(self) -> str:
        return self._corpus.name

    def ask(self, question: str) -> AskResponse:
        return self.ask_with_context(question)[0]

    def ask_with_context(self, question: str) -> tuple[AskResponse, list[Chunk]]:
        """Like ask(), but also returns the full retrieved chunks (used by evaluation)."""
        chunks = self._retriever.retrieve(question, self._top_k)
        if not chunks:
            fallback = AskResponse(
                answer=FALLBACK_ANSWER,
                citations=[],
                corpus=self._corpus.name,
                answered_from_context=False,
            )
            return fallback, []
        context = format_context([(c.page, c.text) for c in chunks])
        answer = self._llm.complete(
            SYSTEM_PROMPT, USER_TEMPLATE.format(context=context, question=question)
        )
        pages = cited_pages(answer)
        citations = [
            Citation(
                source=self._corpus.display_name,
                page=c.page,
                snippet=c.text[:SNIPPET_CHARS].strip(),
                cited=c.page in pages,
            )
            for c in chunks
        ]
        response = AskResponse(
            answer=answer,
            citations=citations,
            corpus=self._corpus.name,
            answered_from_context=FALLBACK_ANSWER not in answer,
        )
        return response, chunks
