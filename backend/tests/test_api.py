from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.rag.service import AssistantService
from app.rag.store import Chunk
from tests.fakes import TEST_CORPUS, FakeLLM, FakeRetriever


def client(llm: FakeLLM | None = None, limit: int = 10) -> TestClient:
    service = AssistantService(
        FakeRetriever([Chunk("Appendectomy text", 175)]),
        llm or FakeLLM("Appendectomy [Source Page: 175]."),
        TEST_CORPUS,
        top_k=5,
    )
    return TestClient(create_app(service, Settings(rate_limit_per_minute=limit)))


def test_health_reports_corpus_and_index_size():
    with client() as c:
        assert c.get("/api/health").json() == {
            "status": "ok",
            "corpus": "test",
            "indexed_chunks": 1,
        }


def test_ask_returns_answer_with_citations_and_disclaimer():
    with client() as c:
        body = c.post("/api/ask", json={"question": "  appendicitis treatment?  "}).json()
    assert body["answer"].startswith("Appendectomy")
    assert body["citations"][0] == {
        "source": "Test Manual",
        "document": "Test Manual",
        "citation_label": "Test Manual",
        "page": 175,
        "snippet": "Appendectomy text",
        "cited": True,
    }
    assert "Not medical advice" in body["disclaimer"]


def test_ask_rejects_blank_and_oversized_questions():
    with client() as c:
        assert c.post("/api/ask", json={"question": "   "}).status_code == 422
        assert c.post("/api/ask", json={"question": "x" * 1001}).status_code == 422


def test_ask_is_rate_limited():
    with client(limit=2) as c:
        codes = [c.post("/api/ask", json={"question": "abc?"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_llm_failure_returns_502_without_leaking_details():
    with client(llm=FakeLLM(fail=True)) as c:
        resp = c.post("/api/ask", json={"question": "abc?"})
    assert resp.status_code == 502
    assert "boom" not in resp.text
