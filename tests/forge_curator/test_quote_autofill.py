from __future__ import annotations

import pytest

from scripts.forge_curator.quote_autofill import classify_quote_autofill


@pytest.mark.parametrize(
    ("quote", "expected_outcome", "expected_constellation"),
    [
        ("the Capstone constellation passed by", "miss", "Capstone"),
        ("The Magic constellation missed a connection", "miss", "Magic"),
        (
            "A connection formed with the Quality constellation before I moved on.",
            "hit",
            "Quality",
        ),
        (
            "I felt a connection being made to the Personal Reality constellation, "
            "followed by a significant tremor. Shortly after it passed, I stood.",
            "hit",
            "Personal Reality",
        ),
    ],
)
def test_quote_autofill_detects_single_constellation_and_clear_outcome(
    quote: str,
    expected_outcome: str,
    expected_constellation: str,
) -> None:
    suggestion = classify_quote_autofill(quote)

    assert suggestion is not None
    assert suggestion.outcome == expected_outcome
    assert suggestion.constellation == expected_constellation


@pytest.mark.parametrize(
    "quote",
    [
        "the Capstone constellation and the Magic constellation passed by",
        "the constellation passed by without naming which one",
        "the Capstone constellaton passed by",
        "the Capstone constellation shimmered nearby",
    ],
)
def test_quote_autofill_rejects_ambiguous_or_unclear_quotes(quote: str) -> None:
    assert classify_quote_autofill(quote) is None
