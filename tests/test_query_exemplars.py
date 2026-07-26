from __future__ import annotations

from scripts.query_exemplars import retrieve


def _entry(chapter_num: str, regime_tags: list[int]) -> dict:
    return {
        "chapter_num": chapter_num,
        "regime_tags": regime_tags,
        "is_boundary": len(regime_tags) > 1,
        "rolls": [],
    }


def _index() -> dict:
    return {
        "schema_version": 1,
        "exemplars": [
            _entry("10", [1]),
            _entry("50", [1]),
            _entry("95", [2]),
            _entry("97", [2, 3]),  # boundary entry
            _entry("100", [3]),
            _entry("120", [3]),
        ],
        "statistics": {},
    }


def test_retrieve_returns_only_same_regime_exemplars() -> None:
    index = _index()

    regime_1 = retrieve(1, index)
    regime_2 = retrieve(2, index)
    regime_3 = retrieve(3, index)

    assert {e["chapter_num"] for e in regime_1} == {"10", "50"}
    assert {e["chapter_num"] for e in regime_2} == {"95", "97"}
    assert {e["chapter_num"] for e in regime_3} == {"97", "100", "120"}

    for target_regime, results in ((1, regime_1), (2, regime_2), (3, regime_3)):
        for entry in results:
            assert target_regime in entry["regime_tags"], (
                f"retrieve({target_regime}, ...) returned a cross-regime "
                f"exemplar: {entry}"
            )


def test_boundary_entry_visible_for_both_adjacent_regimes() -> None:
    index = _index()

    regime_2 = retrieve(2, index)
    regime_3 = retrieve(3, index)

    assert any(e["chapter_num"] == "97" for e in regime_2)
    assert any(e["chapter_num"] == "97" for e in regime_3)


def test_no_cross_regime_exemplar_ever_returned_across_all_regimes() -> None:
    index = _index()

    for target_regime in (1, 2, 3):
        for entry in retrieve(target_regime, index):
            assert target_regime in entry["regime_tags"]


def test_retrieve_is_deterministic_across_repeated_calls() -> None:
    index = _index()

    first = retrieve(3, index)
    second = retrieve(3, index)

    assert [e["chapter_num"] for e in first] == [e["chapter_num"] for e in second]


def test_retrieve_k_truncates_to_at_most_k_entries() -> None:
    index = _index()

    results = retrieve(3, index, k=2)

    assert len(results) == 2
    for entry in results:
        assert 3 in entry["regime_tags"]


def test_retrieve_sorts_by_proximity_to_target_chapter() -> None:
    index = _index()

    # Regime 3 candidates: 97, 100, 120. Target chapter 101 should put 100
    # first (distance 1), then 97 (distance 4), then 120 (distance 19).
    results = retrieve(3, index, target_chapter="101")

    assert [e["chapter_num"] for e in results] == ["100", "97", "120"]


def test_retrieve_without_target_chapter_sorts_numerically_ascending() -> None:
    index = _index()

    results = retrieve(3, index)

    assert [e["chapter_num"] for e in results] == ["97", "100", "120"]
