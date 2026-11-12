from app.ingest.cleaning import clean_page_text, compile_patterns

PAGE = """Appendicitis is acute inflammation of the vermiform appendix.
Treatment is surgical removal.
The Merck Manual of Diagnosis & Therapy, 19th Edition Chapter 11. Acute Abdomen
174
someone@example.com
AB12CD34EF
This file is meant for personal use by someone@example.com only.
Sharing or publishing the contents in part or full is liable for legal action."""

HEADER = compile_patterns([r"^The Merck Manual of Diagnosis & Therapy, 19th Edition"])


def test_removes_licence_footer_and_running_header():
    cleaned = clean_page_text(PAGE, HEADER)
    assert "example.com" not in cleaned
    assert "AB12CD34EF" not in cleaned
    assert "liable for legal action" not in cleaned
    assert "Merck Manual of Diagnosis" not in cleaned
    assert cleaned.startswith("Appendicitis is acute inflammation")
    assert "Treatment is surgical removal." in cleaned


def test_keeps_uppercase_clinical_lines_not_following_an_email():
    text = "Order these tests:\nECG\nCBC123\nRepeat in 6 h."
    assert clean_page_text(text) == text


def test_collapses_excess_blank_lines():
    assert clean_page_text("a\n\n\n\n\nb") == "a\n\nb"
