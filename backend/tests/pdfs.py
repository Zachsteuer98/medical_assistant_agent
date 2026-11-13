"""Build tiny PDFs for ingest/download tests (no real corpus files needed)."""

from pathlib import Path

import pymupdf


def make_pdf(path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=9)
    doc.save(path)
    doc.close()
    return path
