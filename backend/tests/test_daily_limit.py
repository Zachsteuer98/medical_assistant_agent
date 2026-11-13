from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.rag.service import AssistantService
from app.rag.store import Chunk
from app.ratelimit import DailyLimiter
from tests.fakes import TEST_CORPUS, FakeLLM, FakeRetriever

ASK = {"question": "abc?"}


def make_limiter(limit: int, start: datetime):
    now = [start]
    return DailyLimiter(limit, clock=lambda: now[0]), now


def test_boundary_allows_exactly_the_limit():
    limiter, _ = make_limiter(3, datetime(2026, 1, 1, 12, tzinfo=UTC))
    assert [limiter.allow() for _ in range(5)] == [True, True, True, False, False]


def test_budget_resets_at_utc_midnight():
    limiter, now = make_limiter(1, datetime(2026, 1, 1, 23, 59, 59, tzinfo=UTC))
    assert limiter.allow()
    assert not limiter.allow()
    now[0] = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    assert limiter.allow()


def test_midnight_uses_utc_not_local_offset():
    plus_nine = datetime(2026, 1, 2, 8, 0, tzinfo=UTC).astimezone(timezone_plus(9))
    limiter, now = make_limiter(1, plus_nine)  # 23:00 UTC on Jan 1
    assert limiter.allow()
    now[0] = datetime(2026, 1, 1, 23, 30, tzinfo=UTC).astimezone(timezone_plus(9))
    assert not limiter.allow()


def timezone_plus(hours: int):
    from datetime import timezone

    return timezone(timedelta(hours=hours))


def test_seconds_until_reset():
    limiter, now = make_limiter(1, datetime(2026, 1, 1, 23, 0, tzinfo=UTC))
    assert limiter.seconds_until_reset() == 3600
    now[0] = datetime(2026, 1, 1, 23, 59, 59, 500000, tzinfo=UTC)
    assert limiter.seconds_until_reset() == 1
    now[0] = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert limiter.seconds_until_reset() == 86400


def api_client(daily: int, per_minute: int = 100) -> TestClient:
    service = AssistantService(
        FakeRetriever([Chunk("text", 1)]), FakeLLM("A [Source Page: 1]."), TEST_CORPUS, top_k=5
    )
    settings = Settings(rate_limit_per_minute=per_minute, daily_question_limit=daily)
    return TestClient(create_app(service, settings))


def test_api_returns_429_with_retry_after_when_cap_hit():
    with api_client(daily=2) as c:
        codes = [c.post("/api/ask", json=ASK).status_code for _ in range(3)]
        resp = c.post("/api/ask", json=ASK)
    assert codes == [200, 200, 429]
    assert "daily demo limit" in resp.json()["detail"]
    assert 1 <= int(resp.headers["retry-after"]) <= 86400


def test_cap_does_not_take_health_down():
    with api_client(daily=1) as c:
        c.post("/api/ask", json=ASK)
        assert c.post("/api/ask", json=ASK).status_code == 429
        assert c.get("/api/health").status_code == 200


def test_per_minute_rejection_does_not_consume_daily_budget():
    # per-minute 1, daily 2: the rejected 2nd request must leave one daily slot for a new client.
    with api_client(daily=2, per_minute=1) as c:
        assert c.post("/api/ask", json=ASK).status_code == 200
        assert c.post("/api/ask", json=ASK).status_code == 429  # per-minute
        other = {"x-forwarded-for": "9.9.9.9"}
        assert c.post("/api/ask", json=ASK, headers=other).status_code == 200  # daily slot 2
        third = {"x-forwarded-for": "8.8.8.8"}
        resp = c.post("/api/ask", json=ASK, headers=third)
    assert resp.status_code == 429
    assert "daily" in resp.json()["detail"]


def test_invalid_daily_limit_fails_at_startup():
    import pytest

    for bad in (0, -5):
        with pytest.raises(ValueError):
            Settings(daily_question_limit=bad)
