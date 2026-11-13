"""CLI: fetch a corpus's PDFs from its pinned manifest.

    uv run python -m app.download --corpus public

URLs, SHA-256 digests and page counts are pinned in app/corpus_manifests/<corpus>.json, so
downloads are deterministic and nothing is scraped at runtime. Files already present with
the pinned digest are skipped. Any failure (HTTP error, non-PDF response, digest or page-count
mismatch) aborts with a non-zero exit code.
"""

import argparse
import hashlib
import http.client
import logging
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pymupdf

from app.corpora import ManifestEntry, load_manifest, manifest_pdf_path

# Generic browser UA: the VA site serves PDFs to it; no project or personal details.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
TIMEOUT_S = 60.0
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 2.0  # waits 2, 4, 8 s between attempts
READ_BLOCK_BYTES = 1 << 16
PDF_MAGIC = b"%PDF-"
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# ADR 0004: re-check front matter for reproduction restrictions at download time.
FRONT_MATTER_PAGES = 6
_RESTRICTION_NOTICE = re.compile(r"(?i)copyright|©|all rights reserved|may not be reproduced")

log = logging.getLogger("download")
Fetcher = Callable[[str], bytes]


class DownloadError(RuntimeError):
    """A pinned corpus file could not be fetched or failed verification."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_with_retries(url: str, sleep: Callable[[float], None] = time.sleep) -> bytes:
    """GET url; retry transient failures with exponential backoff, fail fast on others."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
            if "pdf" not in content_type.lower():
                raise DownloadError(f"{url}: expected a PDF, got Content-Type {content_type!r}")
            return body
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                raise DownloadError(f"{url}: HTTP {exc.code}") from exc
            reason = f"HTTP {exc.code}"
        except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise DownloadError(f"{url}: {exc}") from exc
            reason = str(exc)
        wait = BACKOFF_BASE_S * 2 ** (attempt - 1)
        log.warning("retrying url=%s attempt=%d reason=%s wait_s=%.0f", url, attempt, reason, wait)
        sleep(wait)
    raise AssertionError("unreachable")


def verify_pdf(path: Path, entry: ManifestEntry) -> None:
    with path.open("rb") as fh:
        if fh.read(len(PDF_MAGIC)) != PDF_MAGIC:
            raise DownloadError(f"{path}: not a PDF (missing {PDF_MAGIC!r} header)")
    digest = sha256_of(path)
    if digest != entry.sha256:
        raise DownloadError(
            f"{path}: sha256 {digest} != pinned {entry.sha256}. The publisher may have "
            "re-issued the file; re-check it and update the manifest deliberately."
        )
    with pymupdf.open(path) as doc:
        pages = doc.page_count
        front = "".join(doc[i].get_text() for i in range(min(FRONT_MATTER_PAGES, pages)))
    if pages != entry.pages:
        raise DownloadError(f"{path}: {pages} pages, manifest pins {entry.pages}")
    if _RESTRICTION_NOTICE.search(front):
        log.warning("front matter mentions copyright/reproduction terms; review file=%s", path)


def download_entry(entry: ManifestEntry, dest: Path, fetch: Fetcher = fetch_with_retries) -> bool:
    """Ensure dest holds the pinned file. Returns True if it was downloaded, False if skipped."""
    if dest.exists():
        if sha256_of(dest) == entry.sha256:
            log.info("skip id=%s (already present)", entry.id)
            return False
        log.warning("re-downloading id=%s: existing file does not match pinned sha256", entry.id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = fetch(entry.url)
    if not body.startswith(PDF_MAGIC):
        raise DownloadError(f"{entry.url}: response body is not a PDF")
    partial = dest.with_suffix(dest.suffix + ".part")
    partial.write_bytes(body)
    try:
        verify_pdf(partial, entry)
    except DownloadError:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(dest)  # atomic: a crash never leaves a truncated file under the final name
    log.info("downloaded id=%s bytes=%d", entry.id, len(body))
    return True


def download_corpus(corpus_name: str, fetch: Fetcher = fetch_with_retries) -> int:
    """Download every manifest entry; returns the number of files fetched."""
    entries = load_manifest(corpus_name)
    return sum(download_entry(e, manifest_pdf_path(corpus_name, e), fetch) for e in entries)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="public", help="Corpus with a pinned manifest")
    args = parser.parse_args()
    try:
        fetched = download_corpus(args.corpus)
    except (DownloadError, FileNotFoundError) as exc:
        log.error("download failed: %s", exc)
        sys.exit(1)
    log.info("done corpus=%s fetched=%d", args.corpus, fetched)


if __name__ == "__main__":
    main()
