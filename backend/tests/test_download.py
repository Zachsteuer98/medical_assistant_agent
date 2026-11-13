import email.message
import hashlib
import io
import urllib.error
from pathlib import Path

import pytest

from app import download
from app.corpora import ManifestEntry
from app.download import DownloadError, download_entry, fetch_with_retries
from tests.pdfs import make_pdf

URL = "https://example.invalid/guideline.pdf"


@pytest.fixture
def pdf_bytes(tmp_path: Path) -> bytes:
    return make_pdf(tmp_path / "src.pdf", ["one", "two"]).read_bytes()


def entry_for(body: bytes, pages: int = 2) -> ManifestEntry:
    return ManifestEntry(
        id="g",
        title="Guideline",
        year=2025,
        citation_label="G",
        url=URL,
        sha256=hashlib.sha256(body).hexdigest(),
        pages=pages,
        first_content_page=0,
    )


class FakeFetch:
    def __init__(self, body: bytes):
        self.body = body
        self.calls = 0

    def __call__(self, url: str) -> bytes:
        self.calls += 1
        return self.body


def test_downloads_verifies_and_writes_file(tmp_path: Path, pdf_bytes: bytes):
    dest = tmp_path / "out" / "g.pdf"
    assert download_entry(entry_for(pdf_bytes), dest, FakeFetch(pdf_bytes)) is True
    assert dest.read_bytes() == pdf_bytes


def test_skips_file_already_present_with_pinned_digest(tmp_path: Path, pdf_bytes: bytes):
    dest = tmp_path / "g.pdf"
    dest.write_bytes(pdf_bytes)
    fetch = FakeFetch(b"unused")
    assert download_entry(entry_for(pdf_bytes), dest, fetch) is False
    assert fetch.calls == 0


def test_replaces_stale_file_whose_digest_differs(tmp_path: Path, pdf_bytes: bytes):
    dest = tmp_path / "g.pdf"
    dest.write_bytes(b"%PDF- old version")
    assert download_entry(entry_for(pdf_bytes), dest, FakeFetch(pdf_bytes)) is True
    assert dest.read_bytes() == pdf_bytes


def test_rejects_html_masquerading_as_pdf(tmp_path: Path, pdf_bytes: bytes):
    dest = tmp_path / "out" / "g.pdf"
    with pytest.raises(DownloadError, match="not a PDF"):
        download_entry(entry_for(pdf_bytes), dest, FakeFetch(b"<html>blocked</html>"))
    assert not dest.parent.exists() or list(dest.parent.iterdir()) == []


def test_rejects_digest_mismatch_and_leaves_no_partial_file(tmp_path: Path, pdf_bytes: bytes):
    dest = tmp_path / "out" / "g.pdf"
    with pytest.raises(DownloadError, match="sha256"):
        download_entry(entry_for(b"something else"), dest, FakeFetch(pdf_bytes))
    assert list(dest.parent.iterdir()) == []


def test_rejects_page_count_mismatch(tmp_path: Path, pdf_bytes: bytes):
    with pytest.raises(DownloadError, match="2 pages, manifest pins 165"):
        download_entry(entry_for(pdf_bytes, pages=165), tmp_path / "g.pdf", FakeFetch(pdf_bytes))


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, content_type: str):
        super().__init__(body)
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "err", email.message.Message(), None)


def scripted_urlopen(monkeypatch, outcomes: list):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(download.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_fetch_retries_transient_errors_with_exponential_backoff(monkeypatch):
    calls = scripted_urlopen(
        monkeypatch,
        [
            http_error(503),
            urllib.error.URLError("reset"),
            FakeResponse(b"%PDF-x", "application/pdf"),
        ],
    )
    sleeps: list[float] = []
    assert fetch_with_retries(URL, sleep=sleeps.append) == b"%PDF-x"
    assert sleeps == [2.0, 4.0]
    assert calls[0].get_header("User-agent") == download.USER_AGENT


def test_fetch_does_not_retry_client_errors(monkeypatch):
    scripted_urlopen(monkeypatch, [http_error(404)])
    sleeps: list[float] = []
    with pytest.raises(DownloadError, match="HTTP 404"):
        fetch_with_retries(URL, sleep=sleeps.append)
    assert sleeps == []


def test_fetch_gives_up_after_max_attempts(monkeypatch):
    scripted_urlopen(monkeypatch, [http_error(503)] * download.MAX_ATTEMPTS)
    with pytest.raises(DownloadError, match="HTTP 503"):
        fetch_with_retries(URL, sleep=lambda _: None)


def test_fetch_rejects_non_pdf_content_type(monkeypatch):
    scripted_urlopen(monkeypatch, [FakeResponse(b"<html>", "text/html")])
    with pytest.raises(DownloadError, match="expected a PDF"):
        fetch_with_retries(URL, sleep=lambda _: None)
