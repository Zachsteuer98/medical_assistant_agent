"""Strip licence watermarks and layout noise from extracted PDF page text.

Watermarks are matched by structure, not by literal personal values, so no
licensee details ever need to live in source control.
"""

import re
from collections.abc import Iterable

_EMAIL_LINE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Licence IDs only count as watermark when they directly follow an email-only line.
_LICENCE_ID_LINE = re.compile(r"[A-Z0-9]{6,16}")
_GENERIC_NOISE = (
    re.compile(r"^This file is meant for personal use by \S+ only\.$"),
    re.compile(
        r"^Sharing or publishing the contents in part or full is liable for legal action\.$"
    ),
)
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def compile_patterns(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns if p)


def clean_page_text(text: str, noise_patterns: tuple[re.Pattern[str], ...] = ()) -> str:
    kept: list[str] = []
    previous_was_email = False
    for line in text.splitlines():
        stripped = line.strip()
        if previous_was_email and _LICENCE_ID_LINE.fullmatch(stripped):
            previous_was_email = False
            continue
        previous_was_email = bool(_EMAIL_LINE.fullmatch(stripped))
        if previous_was_email:
            continue
        if any(p.search(stripped) for p in _GENERIC_NOISE + noise_patterns):
            continue
        kept.append(line)
    return _EXCESS_BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()
