import pytest

from evaluation.judge import JudgeOutputError, parse_verdict


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
