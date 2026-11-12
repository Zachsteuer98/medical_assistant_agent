"""Registry of supported corpora. Each corpus has its own vector collection (ADR 0001)."""

from dataclasses import dataclass
from pathlib import Path

from app.config import REPO_ROOT


@dataclass(frozen=True)
class CorpusSpec:
    name: str
    display_name: str
    pdf_path: Path
    # 0-based index of the first clinical page; earlier pages are cover/TOC "retrieval traps".
    first_content_page: int
    # Regexes for lines that are layout noise (running headers etc.), not content.
    noise_line_patterns: tuple[str, ...] = ()


CORPORA: dict[str, CorpusSpec] = {
    "merck": CorpusSpec(
        name="merck",
        display_name="The Merck Manual of Diagnosis & Therapy, 19th ed.",
        pdf_path=REPO_ROOT / "data" / "raw" / "merck.pdf",
        first_content_page=52,
        noise_line_patterns=(r"^The Merck Manual of Diagnosis & Therapy, 19th Edition",),
    ),
}


def get_corpus(name: str) -> CorpusSpec:
    try:
        return CORPORA[name]
    except KeyError as exc:
        raise ValueError(f"Unknown corpus {name!r}; expected one of {sorted(CORPORA)}") from exc
