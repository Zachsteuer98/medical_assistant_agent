import json

import pytest

from evaluation.judge import (
    GRADE_SCORES,
    JudgeOutputError,
    format_facts,
    parse_correctness,
    parse_verdict,
)


def test_parses_valid_verdict():
    v = parse_verdict('{"score": 4, "rationale": "Mostly supported."}')
    assert (v.score, v.rationale) == (4, "Mostly supported.")


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"score": 6, "rationale": "x"}',
        '{"score": 0, "rationale": "x"}',
        '{"rationale": "x"}',
    ],
)
def test_rejects_malformed_or_out_of_range(raw):
    with pytest.raises(JudgeOutputError):
        parse_verdict(raw)


# --- correctness ------------------------------------------------------------------------


def _correctness(facts, contradiction=False):
    return json.dumps(
        {
            "facts": facts,
            "contradiction": contradiction,
            "contradiction_detail": "quote" if contradiction else "",
            "rationale": "r",
        }
    )


@pytest.mark.parametrize(
    ("facts", "contradiction", "grade", "coverage"),
    [
        (["yes", "yes"], False, "pass", 1.0),
        (["yes", "partly"], False, "partial", 0.75),
        (["no", "partly"], False, "partial", 0.25),
        (["no", "no"], False, "fail", 0.0),
        (["yes", "yes"], True, "fail", 1.0),  # a contradiction fails even with full coverage
    ],
)
def test_correctness_grade_rubric(facts, contradiction, grade, coverage):
    v = parse_correctness(_correctness(facts, contradiction), n_facts=2)
    assert (v.grade, v.coverage, v.score) == (grade, coverage, GRADE_SCORES[grade])


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        _correctness(["yes"]),  # wrong number of labels
        _correctness(["yes", "maybe"]),  # unknown label
        json.dumps({"facts": ["yes", "yes"], "contradiction": "false", "rationale": "r"}),
        json.dumps({"facts": ["yes", "yes"], "rationale": "r"}),
    ],
)
def test_rejects_malformed_correctness_output(raw):
    with pytest.raises(JudgeOutputError):
        parse_correctness(raw, n_facts=2)


def test_format_facts_numbers_each_fact():
    assert format_facts(("a", "b")) == "1. a\n2. b"
