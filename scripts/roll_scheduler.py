"""Per-chapter roll scheduler.

Given a chapter's predicted roll slots and the in-order list of paid hits,
decide which K of the N slots are hits such that available CP at each
chosen slot is >= the hit's cost.

Pure backtracking solver. ``schedule_chapter`` is side-effect-free; the
caller integrates results into roll_facts.json.

Picks the **latest-feasible** assignment: among all feasible slot
selections, choose the one where each hit's slot index is the latest
possible. This reflects "spend when forced" and is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Import the regime simulator. When this module is imported via the
# package path (``scripts.roll_scheduler``), use the package-qualified
# import. When run as a script with ``scripts/`` on sys.path, use the
# bare import. Both forms exist in the repo.
try:
    from scripts.regime_simulator import (
        REGIMES,
        RegimeSegment,
        ShadowState,
        _accumulate_x100,
        regime_for_chapter,
        shadow_words,
    )
except ImportError:  # pragma: no cover - fallback for script-mode runs
    from regime_simulator import (  # type: ignore[no-redef]
        REGIMES,
        RegimeSegment,
        ShadowState,
        _accumulate_x100,
        regime_for_chapter,
        shadow_words,
    )


@dataclass
class SlotInput:
    """One predicted roll slot (chapter-local word_position)."""
    word_position: int
    roll_trigger_cp_threshold: int
    source: str = "predicted"   # "predicted" | "synthetic"


@dataclass
class HitInput:
    """One paid acquisition unit, in narrative order.

    For multi-grab rolls, ``paid_perks`` holds the full list of paid
    perks merged into this single roll; ``cost`` is the SUM of those
    paid costs (what the Forge actually debits). ``perk`` is a legacy
    convenience field set to the principal (largest-cost) paid perk.
    """
    cost: int
    perk: dict | None = None    # opaque payload preserved by caller (principal)
    paid_perks: list[dict] = field(default_factory=list)
    free_perks: list[dict] = field(default_factory=list)
    mention_chapter_num: str | None = None
    mention_word_position: int | None = None
    display_position_policy: str = "mechanical"
    evidence_quotes: list[dict] = field(default_factory=list)


@dataclass
class Assignment:
    """One slot's resolved state in the scheduler's chosen plan."""
    slot_index: int
    word_position: int
    roll_trigger_cp_threshold: int
    available_cp: int           # banked CP just BEFORE this slot
    banked_cp_after_roll: int   # banked CP just AFTER this slot
    outcome: str                # "hit" | "miss"
    hit_index: int | None       # index into hits if outcome == "hit"


@dataclass
class ScheduleResult:
    feasible: bool
    assignments: list[Assignment]
    slack: int = 0              # sum over hits of (avail_cp - cost); lower = tighter
    ambiguity: int = 0          # count of distinct feasible assignments (cap 50)
    diagnostic: str = ""        # populated when not feasible
    explanation: str = ""
    banked_cp_out: int | None = None
    shadow_out: ShadowState | None = None


def _walk_pre_debit_cp(
    slots: list[SlotInput],
    chapter_words: int,
    regime: int,
    banked_cp_in: int,
    shadow_in: ShadowState,
    hit_assignments: dict[int, int],     # slot_idx -> hit_cost (debited at slot)
    segments: list[RegimeSegment] | None = None,
) -> tuple[list[int], int, ShadowState]:
    """Walk slots in word order, returning per-slot pre-debit available CP.

    Applies hits' debits and shadow effects in-place; returns the final
    banked CP (chapter-end) and final shadow state. ``segments`` lets a
    chapter switch regimes mid-walk (for ch 97 specifically). When
    omitted, the entire chapter uses ``regime``.
    """
    state = shadow_in.copy()
    banked_x100 = banked_cp_in * 100
    last = 0
    pre_debit: list[int] = []
    seg_list = list(segments or [RegimeSegment(regime=regime, end_word_local=None)])
    seg_idx = 0
    current_regime = seg_list[seg_idx].regime

    def _walk_to(target: int) -> None:
        """Accumulate CP up to chapter-local word ``target``, advancing
        through regime segments as needed."""
        nonlocal banked_x100, last, seg_idx, current_regime
        while last < target:
            seg_end = seg_list[seg_idx].end_word_local
            if seg_end is None or seg_end >= target:
                step = target - last
                if step > 0:
                    banked_x100 = _accumulate_x100(
                        step, current_regime, banked_x100, state,
                    )
                last = target
                return
            step = seg_end - last
            if step > 0:
                banked_x100 = _accumulate_x100(
                    step, current_regime, banked_x100, state,
                )
            last = seg_end
            seg_idx += 1
            current_regime = seg_list[seg_idx].regime

    for idx, slot in enumerate(slots):
        _walk_to(slot.word_position)
        pre_debit.append(banked_x100 // 100)
        if idx in hit_assignments:
            cost = hit_assignments[idx]
            banked_x100 -= cost * 100
            if banked_x100 < 0:
                banked_x100 = 0
            sw = shadow_words(cost, current_regime)
            if sw:
                state.remaining += sw
    if chapter_words > last:
        _walk_to(chapter_words)
    return pre_debit, banked_x100 // 100, state


def schedule_chapter(
    chapter_num: str,
    slots: list[SlotInput],
    hits: list[HitInput],
    banked_cp_in: int,
    shadow_in: ShadowState | None = None,
    chapter_words: int = 0,
    ambiguity_cap: int = 50,
    segments: list[RegimeSegment] | None = None,
) -> ScheduleResult:
    """Solve which slots are hits.

    Returns a `ScheduleResult` with feasibility, per-slot assignments,
    slack (tightness measure), and ambiguity count. ``segments`` lets
    a chapter switch regimes mid-walk; when omitted the chapter's
    primary regime is used throughout.
    """
    regime = regime_for_chapter(chapter_num)
    state_in = shadow_in or ShadowState()
    n = len(slots)
    k = len(hits)

    if k == 0:
        # All misses. Walk to stamp pre-debit CP.
        pre_debit, banked_out, shadow_out = _walk_pre_debit_cp(
            slots, chapter_words, regime, banked_cp_in, state_in, {},
            segments=segments,
        )
        assignments = [
            Assignment(
                slot_index=i,
                word_position=s.word_position,
                roll_trigger_cp_threshold=s.roll_trigger_cp_threshold,
                available_cp=pre_debit[i],
                banked_cp_after_roll=pre_debit[i],
                outcome="miss",
                hit_index=None,
            )
            for i, s in enumerate(slots)
        ]
        return ScheduleResult(
            feasible=True, assignments=assignments,
            slack=0, ambiguity=1,
            banked_cp_out=banked_out,
            shadow_out=shadow_out,
        )

    if k > n:
        # Caller should have synthesized extra slots; surface as
        # infeasible if not.
        return ScheduleResult(
            feasible=False, assignments=[], slack=0, ambiguity=0,
            diagnostic="regime_or_section_misclassification",
            explanation=(
                f"Chapter has {n} predicted/synth slots but {k} recorded "
                f"paid hits."
            ),
        )

    # ---- backtracking solver --------------------------------------------
    # Try slot indices in DESCENDING order for latest-feasible bias.
    best_solution: list[int] | None = None
    feasible_count = [0]

    def feasible_at(slot_idx: int, hit_idx: int, partial: dict[int, int]) -> int | None:
        """Return pre-debit available_cp at slot_idx given partial
        hit_assignments, or None if shortfall."""
        partial2 = dict(partial)
        # Walk just enough — do a full walk for simplicity (n<=10 makes
        # this trivial).
        pre, _, _ = _walk_pre_debit_cp(
            slots, chapter_words, regime, banked_cp_in, state_in, partial2,
            segments=segments,
        )
        return pre[slot_idx]

    def dfs(hit_idx: int, min_slot: int, picked: list[int],
            partial: dict[int, int]) -> None:
        nonlocal best_solution
        if feasible_count[0] >= ambiguity_cap and best_solution is not None:
            return
        if hit_idx == k:
            if best_solution is None:
                best_solution = list(picked)
            feasible_count[0] += 1
            return
        cost = hits[hit_idx].cost
        # Latest-feasible: try the highest slot index first, then descend.
        # Need to leave room for remaining (k-1-hit_idx) hits, so highest
        # is n - 1 - (k - 1 - hit_idx) = n - k + hit_idx.
        max_slot = n - k + hit_idx
        for slot_idx in range(max_slot, min_slot - 1, -1):
            avail = feasible_at(slot_idx, hit_idx, partial)
            if avail is None or avail < cost:
                continue
            partial[slot_idx] = cost
            picked.append(slot_idx)
            dfs(hit_idx + 1, slot_idx + 1, picked, partial)
            picked.pop()
            del partial[slot_idx]

    dfs(0, 0, [], {})

    if best_solution is None:
        return ScheduleResult(
            feasible=False, assignments=[], slack=0, ambiguity=0,
            diagnostic="general_infeasible",
            explanation=(
                f"No feasible hit-to-slot assignment exists for chapter "
                f"{chapter_num} (n={n}, k={k}, banked_cp_in={banked_cp_in})."
            ),
        )

    # Materialize assignments.
    final_partial = {idx: hits[i].cost for i, idx in enumerate(best_solution)}
    pre_debit, banked_out, shadow_out = _walk_pre_debit_cp(
        slots, chapter_words, regime, banked_cp_in, state_in, final_partial,
        segments=segments,
    )
    hit_idx_for_slot = {slot_idx: i for i, slot_idx in enumerate(best_solution)}
    assignments: list[Assignment] = []
    slack = 0
    for i, s in enumerate(slots):
        if i in hit_idx_for_slot:
            hi = hit_idx_for_slot[i]
            cost = hits[hi].cost
            avail = pre_debit[i]
            slack += avail - cost
            after = max(0, avail - cost)
            assignments.append(Assignment(
                slot_index=i,
                word_position=s.word_position,
                roll_trigger_cp_threshold=s.roll_trigger_cp_threshold,
                available_cp=avail,
                banked_cp_after_roll=after,
                outcome="hit",
                hit_index=hi,
            ))
        else:
            avail = pre_debit[i]
            assignments.append(Assignment(
                slot_index=i,
                word_position=s.word_position,
                roll_trigger_cp_threshold=s.roll_trigger_cp_threshold,
                available_cp=avail,
                banked_cp_after_roll=avail,  # miss: no debit
                outcome="miss",
                hit_index=None,
            ))

    return ScheduleResult(
        feasible=True,
        assignments=assignments,
        slack=slack,
        ambiguity=feasible_count[0],
        banked_cp_out=banked_out,
        shadow_out=shadow_out,
    )


def infer_chapter_outcomes(
    predicted_rolls: list[dict],
    paid_perks: list[dict],
    free_perks: list[dict] | None = None,
    override_outcomes: dict[int, str] | None = None,
) -> list[dict]:
    """Apply the paid-perk-count constraint to assign hit/miss outcomes
    to a chapter's predicted rolls.

    Canonical helper for both the pipeline (when applying overrides
    during ``derive_roll_facts``) and the TUI (live display after a
    curation action). The TUI must NOT re-implement this logic locally.

    Inputs (chapter-local):
      - ``predicted_rolls``: list of predicted-roll dicts in
        word_position order. Must carry ``word_position``.
      - ``paid_perks``: paid-perk dicts (free=False) for this chapter,
        in epub_sequence order. Each should carry ``cost`` and
        optionally ``constellation``, ``perk_name`` / ``name``.
      - ``free_perks``: free-perk dicts. Attached to the first inferred
        hit (typical bundling: e.g. ch 1's Access Key / Entrance Hall
        ride along with Workshop).
      - ``override_outcomes``: ``{1-based roll index: "hit" | "miss"}``
        — pinned outcomes the inference must respect.

    Returns one dict per predicted roll, in sequence order:
      ``{index, word_position, outcome, constellation,
        purchased_perks, purchased_perk_cost_total, source}``

    ``source`` ∈ {``"override"``, ``"inferred"``, ``"unknown"``}.

    Constraint: ``count(hits) == len(paid_perks)``. Misses fill the
    rest. When uniquely determined (e.g. one unknown slot, one hit
    remaining) the inference fills it.
    """
    if free_perks is None:
        free_perks = []
    if override_outcomes is None:
        override_outcomes = {}
    target_hits = len(paid_perks)
    n_total = len(predicted_rolls)
    result: list[dict] = []
    for k, pred in enumerate(predicted_rolls, start=1):
        outcome = override_outcomes.get(k, "unknown")
        result.append({
            "index": k,
            "word_position": int(pred["cp_offset"]),
            "outcome": outcome,
            "constellation": None,
            "purchased_perks": [],
            "purchased_perk_cost_total": 0,
            "source": "override" if outcome != "unknown" else "unknown",
        })
    confirmed_hits = sum(1 for r in result if r["outcome"] == "hit")
    confirmed_misses = sum(1 for r in result if r["outcome"] == "miss")
    unknowns = [r for r in result if r["outcome"] == "unknown"]
    hits_remaining = max(0, target_hits - confirmed_hits)
    misses_remaining = max(0, (n_total - target_hits) - confirmed_misses)
    if unknowns and hits_remaining + misses_remaining == len(unknowns):
        if hits_remaining == 0:
            for u in unknowns:
                u["outcome"] = "miss"
                u["source"] = "inferred"
        elif misses_remaining == 0:
            for u in unknowns:
                u["outcome"] = "hit"
                u["source"] = "inferred"
    paid_queue = list(paid_perks)
    free_queue = list(free_perks)
    for r in result:
        if r["outcome"] != "hit":
            continue
        if not paid_queue:
            break
        paid = paid_queue.pop(0)
        name = paid.get("perk_name") or paid.get("name", "?")
        cost = int(paid.get("cost") or 0)
        r["purchased_perks"] = [{"name": name, "cost": cost, "free": False}]
        r["purchased_perk_cost_total"] = cost
        if paid.get("constellation"):
            r["constellation"] = paid["constellation"]
        for fp in free_queue:
            fp_name = fp.get("perk_name") or fp.get("name", "?")
            r["purchased_perks"].append({"name": fp_name, "cost": 0, "free": True})
        free_queue = []
    return result


def diagnose_infeasible(
    chapter_num: str,
    slots: list[SlotInput],
    hits: list[HitInput],
    banked_cp_in: int,
    shadow_in: ShadowState | None = None,
    chapter_words: int = 0,
    segments: list[RegimeSegment] | None = None,
) -> tuple[str, str]:
    """Pick the most likely diagnostic for a chapter that has no
    feasible assignment.

    Priority:
      1. regime_or_section_misclassification
      2. hit_order_inconsistency
      3. cost_typo_suspected
      4. general_infeasible
    """
    n = len(slots)
    k = len(hits)
    state_in = shadow_in or ShadowState()
    regime = regime_for_chapter(chapter_num)

    if k > n:
        return (
            "regime_or_section_misclassification",
            f"Chapter has {n} predicted slots but {k} recorded paid hits "
            f"(short by {k - n} slot(s)). Likely section/regime "
            f"misclassification under-counts CP-earning words.",
        )

    # Total CP available across the chapter (no debits) at the very last slot.
    pre_debit, banked_end, _ = _walk_pre_debit_cp(
        slots, chapter_words, regime, banked_cp_in, state_in, {},
        segments=segments,
    )
    total_cp_required = sum(h.cost for h in hits)
    max_cp_anywhere = max(pre_debit) if pre_debit else 0
    if total_cp_required > banked_end + sum(  # earnings + initial bank
            h.cost for _ in []):
        pass
    if max_cp_anywhere < max(h.cost for h in hits):
        return (
            "regime_or_section_misclassification",
            f"Highest CP achieved in chapter is {max_cp_anywhere}, but "
            f"largest hit costs {max(h.cost for h in hits)}. Predicted "
            f"earnings short by ~{max(h.cost for h in hits) - max_cp_anywhere}.",
        )

    # Check whether a permutation of hits is feasible.
    if k <= 6:
        from itertools import permutations
        for perm in permutations(range(k)):
            permuted = [hits[i] for i in perm]
            r = schedule_chapter(
                chapter_num, slots, permuted,
                banked_cp_in, state_in, chapter_words,
                ambiguity_cap=1, segments=segments,
            )
            if r.feasible and tuple(perm) != tuple(range(k)):
                return (
                    "hit_order_inconsistency",
                    f"Curator order infeasible, but permutation {perm} works.",
                )

    # Single-cost-typo check: if exactly one hit's cost reduced to the
    # next standard cost makes it feasible, suspect a typo.
    standard_costs = [100, 200, 300, 400, 500, 600, 800]
    for i, h in enumerate(hits):
        for sc in standard_costs:
            if sc >= h.cost:
                continue
            mut = list(hits)
            mut[i] = HitInput(cost=sc, perk=h.perk, free_perks=h.free_perks)
            r = schedule_chapter(
                chapter_num, slots, mut,
                banked_cp_in, state_in, chapter_words,
                ambiguity_cap=1, segments=segments,
            )
            if r.feasible:
                return (
                    "cost_typo_suspected",
                    f"Hit #{i} cost {h.cost} -> {sc} would be feasible.",
                )

    return (
        "general_infeasible",
        f"No feasible assignment under any permutation or single-hit cost "
        f"adjustment (n={n}, k={k}, banked_in={banked_cp_in}).",
    )
