from app.rag.prompts import FALLBACK_ANSWER
from app.rag.service import AssistantService, cited_pages
from app.rag.store import Chunk
from tests.fakes import TEST_CORPUS, FakeLLM, FakeRetriever

CHUNKS = [Chunk("Sepsis bundle text", 1308), Chunk("Vasopressor text", 1309)]


def make(answer: str, chunks=CHUNKS) -> tuple[AssistantService, FakeLLM]:
    llm = FakeLLM(answer)
    return AssistantService(FakeRetriever(chunks), llm, TEST_CORPUS, top_k=5), llm


def test_marks_only_pages_the_answer_cites():
    svc, _ = make("Give antibiotics within 1 h [Source Page: 1308].")
    result = svc.ask("sepsis protocol?")
    assert result.answered_from_context
    assert [(c.page, c.cited) for c in result.citations] == [(1308, True), (1309, False)]
    assert result.citations[0].source == "Test Manual"


def test_context_sent_to_llm_includes_page_tags_and_question():
    svc, llm = make("ok")
    svc.ask("sepsis protocol?")
    assert "[Source Page: 1308]" in llm.last_user
    assert "sepsis protocol?" in llm.last_user


def test_fallback_answer_is_flagged_not_answered():
    svc, _ = make(FALLBACK_ANSWER)
    assert svc.ask("unrelated?").answered_from_context is False


def test_no_retrieved_chunks_skips_llm():
    svc, llm = make("should not be used", chunks=[])
    result = svc.ask("anything?")
    assert result.answer == FALLBACK_ANSWER
    assert result.citations == []
    assert llm.last_user is None


def test_cited_pages_parses_spacing_variants():
    assert cited_pages("[Source Page: 3] and [Source Page:12]") == {3, 12}
