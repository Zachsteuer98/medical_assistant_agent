"""Answer a question: retrieve -> prompt -> generate -> attach citations."""

import re

from app.corpora import CorpusSpec
from app.rag.llm import ChatModel
from app.rag.prompts import (
    FALLBACK_ANSWER,
    MULTI_DOC_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
    format_context,
    format_multi_doc_context,
)
from app.rag.store import Chunk, Retriever
from app.schemas import AskResponse, Citation

SNIPPET_CHARS = 300
_CITED_PAGES = re.compile(r"\[Source Pages?:\s*([\d,\s]+)\]")
_CITED_DOC_PAGES = re.compile(r"\[Source:\s*([^\],]+?)\s*,\s*Pages?:\s*([\d,\s]+)\]")
# (normalized document label, page). Single-document corpora use an empty label.
CitationKey = tuple[str, int]


def _split_pages(group: str) -> list[int]:
    return [int(p) for p in group.split(",") if p.strip()]


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def cited_pages(answer: str) -> set[int]:
    return {p for group in _CITED_PAGES.findall(answer) for p in _split_pages(group)}


def cited_document_pages(answer: str) -> set[CitationKey]:
    return {
        (_normalize_label(label), page)
        for label, group in _CITED_DOC_PAGES.findall(answer)
        for page in _split_pages(group)
    }


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

    @property
    def system_prompt(self) -> str:
        return MULTI_DOC_SYSTEM_PROMPT if self._corpus.is_multi_document else SYSTEM_PROMPT

    def format_context(self, chunks: list[Chunk]) -> str:
        if not self._corpus.is_multi_document:
            return format_context([(c.page, c.text) for c in chunks])
        return format_multi_doc_context([(self._label(c), c.page, c.text) for c in chunks])

    def cited_keys(self, answer: str) -> set[CitationKey]:
        """Sources the answer explicitly cites, comparable with _key(chunk)."""
        if not self._corpus.is_multi_document:
            return {("", page) for page in cited_pages(answer)}
        return cited_document_pages(answer)

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
        answer = self._llm.complete(
            self.system_prompt,
            USER_TEMPLATE.format(context=self.format_context(chunks), question=question),
        )
        cited = self.cited_keys(answer)
        citations = [self._citation(c, cited) for c in chunks]
        response = AskResponse(
            answer=answer,
            citations=citations,
            corpus=self._corpus.name,
            answered_from_context=FALLBACK_ANSWER not in answer,
        )
        return response, chunks

    def _citation(self, chunk: Chunk, cited: set[CitationKey]) -> Citation:
        document = self._corpus.document_named(chunk.source)
        return Citation(
            source=self._corpus.display_name,
            document=document.display_name,
            citation_label=document.label,
            page=chunk.page,
            snippet=chunk.text[:SNIPPET_CHARS].strip(),
            cited=self._key(chunk) in cited,
        )

    def _label(self, chunk: Chunk) -> str:
        return self._corpus.document_named(chunk.source).label

    def _key(self, chunk: Chunk) -> CitationKey:
        if not self._corpus.is_multi_document:
            return ("", chunk.page)
        return (_normalize_label(self._label(chunk)), chunk.page)
