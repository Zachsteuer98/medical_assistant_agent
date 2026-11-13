"""Client-IP trust: uvicorn's wildcard proxy mode is spoofable, our hop-based lookup is not."""

import asyncio

from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.clientip import client_ip
from app.config import Settings
from app.main import create_app
from app.rag.service import AssistantService
from app.rag.store import Chunk
from tests.fakes import TEST_CORPUS, FakeLLM, FakeRetriever


def uvicorn_client_host(trusted: str, xff: bytes) -> str:
    seen = {}

    async def app(scope, receive, send):
        seen["client"] = scope["client"]

    scope = {
        "type": "http",
        "client": ("10.0.0.1", 1234),
        "headers": [(b"x-forwarded-for", xff)],
    }
    asyncio.run(ProxyHeadersMiddleware(app, trusted_hosts=trusted)(scope, None, None))
    return seen["client"][0]


def test_uvicorn_wildcard_trust_lets_visitor_spoof_ip():
    # Pinned uvicorn with --forwarded-allow-ips "*" takes the LEFTMOST entry, which the
    # visitor controls even though the real proxy appended the true address on the right.
    assert uvicorn_client_host("*", b"6.6.6.6, 203.0.113.7") == "6.6.6.6"
    assert uvicorn_client_host("*", b"7.7.7.7, 203.0.113.7") == "7.7.7.7"


def test_client_ip_ignores_client_supplied_left_entries():
    assert client_ip("10.0.0.1", ["6.6.6.6, 203.0.113.7"], 1) == "203.0.113.7"
    assert client_ip("10.0.0.1", ["7.7.7.7, 203.0.113.7"], 1) == "203.0.113.7"


def test_client_ip_counts_hops_from_the_right_across_header_lines():
    chain = ["6.6.6.6", "203.0.113.7, 10.1.1.1"]
    assert client_ip("10.0.0.1", chain, 2) == "203.0.113.7"


def test_client_ip_falls_back_to_peer():
    assert client_ip("10.0.0.1", [], 1) == "10.0.0.1"  # no header
    assert client_ip("10.0.0.1", ["1.1.1.1"], 2) == "10.0.0.1"  # chain shorter than hops
    assert client_ip("10.0.0.1", ["1.1.1.1"], 0) == "10.0.0.1"  # no proxy configured
    assert client_ip(None, [], 1) == "unknown"


def test_rotating_forwarded_for_does_not_evade_per_minute_limit():
    service = AssistantService(
        FakeRetriever([Chunk("text", 1)]), FakeLLM("A [Source Page: 1]."), TEST_CORPUS, top_k=5
    )
    settings = Settings(rate_limit_per_minute=2, daily_question_limit=1000)
    with TestClient(create_app(service, settings)) as c:
        codes = [
            c.post(
                "/api/ask",
                json={"question": "abc?"},
                headers={"x-forwarded-for": f"6.6.6.{i}, 203.0.113.7"},
            ).status_code
            for i in range(4)
        ]
    assert codes == [200, 200, 429, 429]
