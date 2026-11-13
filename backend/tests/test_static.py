import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.rag.service import AssistantService
from app.rag.store import Chunk
from app.static import SECURITY_HEADERS
from tests.fakes import TEST_CORPUS, FakeLLM, FakeRetriever

NGINX_CONF = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>spa</html>")
    (root / "assets" / "app-abc123.js").write_text("console.log(1)")
    (root / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("top secret")  # outside the served root
    return root


def make_client(static_dir) -> TestClient:
    service = AssistantService(
        FakeRetriever([Chunk("text", 1)]), FakeLLM("A [Source Page: 1]."), TEST_CORPUS, top_k=5
    )
    return TestClient(create_app(service, Settings(static_dir=static_dir)))


def test_serves_index_at_root_without_caching(dist):
    with make_client(dist) as c:
        resp = c.get("/")
    assert resp.status_code == 200 and "spa" in resp.text
    assert resp.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_cached_long_and_immutable(dist):
    with make_client(dist) as c:
        resp = c.get("/assets/app-abc123.js")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_other_static_files_revalidate(dist):
    with make_client(dist) as c:
        assert c.get("/favicon.svg").headers["cache-control"] == "no-cache"


def test_spa_fallback_for_unknown_paths(dist):
    with make_client(dist) as c:
        resp = c.get("/some/client/route")
    assert resp.status_code == 200 and "spa" in resp.text


def test_missing_asset_is_404_not_html(dist):
    with make_client(dist) as c:
        assert c.get("/assets/missing.js").status_code == 404


def test_unknown_api_paths_404_as_json(dist):
    with make_client(dist) as c:
        for path in ("/api/nope", "/api", "/api/"):
            resp = c.get(path)
            assert resp.status_code == 404
            assert resp.headers["content-type"] == "application/json"
            assert "detail" in resp.json()


def test_api_routes_not_shadowed(dist):
    with make_client(dist) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.post("/api/ask", json={"question": "abc?"}).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/..%2fsecret.txt",
        "/%2e%2e/secret.txt",
        "/%2e%2e%2fsecret.txt",
        "/assets/..%2f..%2fsecret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
        "/%252e%252e/secret.txt",
        "//etc/passwd",
        "/%00",
        "/assets/..%5c..%5csecret.txt",
    ],
)
def test_path_traversal_never_leaks_files_outside_root(dist, path):
    with make_client(dist) as c:
        resp = c.get(path)
    assert "top secret" not in resp.text
    assert "root:" not in resp.text


def test_symlink_escaping_root_is_not_served(dist):
    (dist / "link.txt").symlink_to(dist.parent / "secret.txt")
    with make_client(dist) as c:
        resp = c.get("/link.txt")
    assert "top secret" not in resp.text


def test_static_responses_carry_security_headers(dist):
    with make_client(dist) as c:
        for path in ("/", "/assets/app-abc123.js", "/deep/link"):
            headers = c.get(path).headers
            for name, value in SECURITY_HEADERS.items():
                assert headers[name] == value


def test_security_headers_match_nginx_conf():
    conf = NGINX_CONF.read_text()
    declared = {
        name: quoted or bare
        for name, quoted, bare in re.findall(r'add_header (\S+) (?:"([^"]+)"|(\S+)) always;', conf)
    }
    assert declared == SECURITY_HEADERS


def test_unset_static_dir_leaves_api_only(dist):
    with make_client(None) as c:
        assert c.get("/").status_code == 404
        assert c.get("/api/health").status_code == 200


def test_nonexistent_static_dir_is_ignored(tmp_path):
    with make_client(tmp_path / "missing") as c:
        assert c.get("/").status_code == 404


def test_blank_static_dir_env_is_unset(monkeypatch):
    monkeypatch.setenv("STATIC_DIR", "")
    assert Settings().static_dir is None
