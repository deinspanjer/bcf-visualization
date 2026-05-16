from __future__ import annotations

import re

from scripts.forge_curator.evidence_scorer import (
    EVIDENCE_CANDIDATE_THRESHOLD,
    evidence_candidates,
    score_paragraph,
)


def _word_offsets(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in re.finditer(r"\S+", text)]


def test_evidence_scorer_is_case_insensitive_and_word_bounded() -> None:
    score, terms = score_paragraph(
        "The Alchemy constellation passed by without connection."
    )

    assert score >= EVIDENCE_CANDIDATE_THRESHOLD
    assert "constellation" in terms
    assert "passed" in terms
    assert "connection" in terms

    passenger_score, passenger_terms = score_paragraph(
        "My passenger was worried about normal travel."
    )
    assert "pass" not in passenger_terms
    assert passenger_score < EVIDENCE_CANDIDATE_THRESHOLD


def test_evidence_scorer_matches_singular_and_plural_mote_terms() -> None:
    singular_score, singular_terms = score_paragraph(
        "A mote from the Forge reached toward my power."
    )
    plural_score, plural_terms = score_paragraph(
        "Motes from the Forge reached toward my power."
    )

    assert singular_score >= EVIDENCE_CANDIDATE_THRESHOLD
    assert plural_score >= EVIDENCE_CANDIDATE_THRESHOLD
    assert "mote" in singular_terms
    assert "Motes" in plural_terms


def test_evidence_candidates_return_paragraph_start_words() -> None:
    text = (
        "Normal paragraph about tools.\n\n"
        "The Celestial Forge missed a connection to the Size constellation.\n\n"
        "Another normal paragraph."
    )

    candidates = evidence_candidates(text, _word_offsets(text))

    assert len(candidates) == 1
    assert candidates[0].paragraph_index == 1
    assert candidates[0].word_index == 4
    assert candidates[0].score >= EVIDENCE_CANDIDATE_THRESHOLD
