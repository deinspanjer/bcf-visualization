"""Shared regime simulator for the Forge mechanic.

Single source of truth for CP accumulation arithmetic across the three
documented regimes (1, 2, 3) and the regime-3 shadow mechanic. Used by:

  * scripts/predict_rolls.py — full-story walk to predict roll positions.
  * scripts/derive_roll_outcomes.py — to stamp true `available_cp` /
    `banked_cp_after_roll` on interpolated rolls.

The arithmetic uses banked CP * 100 internally to avoid float drift; the
public API exposes plain integer CP values.

Regimes
-------

  Regime 1 (ch 1-91):   100 CP per 2000 words, roll every 100 CP.
  Regime 2 (ch 92-96):  100 CP per 2000 words, roll every 200 CP.
  Regime 3 (ch 97+):    100 CP per 3000 words, roll every 200 CP, plus
                        a shadow window after each 600/800-CP perk during
                        which no CP is banked.

Mid-chapter regime transitions (e.g. ch 97 flips from regime 2 to regime
3 after the Nano-Forge acquisition) are configured in
``data/manual/regime_transitions.json`` and resolved per-chapter via
``regimes_for_chapter``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


# (words_per_100_cp, cp_per_roll). Author's notes for ch91 and ch97
# define these.
REGIMES: dict[int, dict[str, int]] = {
    1: {"words_per_100_cp": 2000, "cp_per_roll": 100},
    2: {"words_per_100_cp": 2000, "cp_per_roll": 200},
    3: {"words_per_100_cp": 3000, "cp_per_roll": 200},
}
SHADOW_CP_RATIO = 0.5    # half the perk's cost worth of CP is the shadow


def regime_for_chapter(chapter_num: str) -> int:
    """Return the chapter's *primary* regime (the regime in effect at the
    start of the chapter). Mid-chapter transitions are returned by
    :func:`regimes_for_chapter` instead.

    Note: ch 97 is special. Its primary regime is 2 (the rate change to
    regime 3 happens mid-chapter, after the Nano-Forge acquisition); the
    ``data/manual/regime_transitions.json`` entry encodes that flip. For
    chapters >= 98 we return 3 unconditionally.
    """
    major = int(chapter_num.split(".")[0])
    if major <= 91:
        return 1
    if major <= 96:
        return 2
    if major == 97:
        return 2  # primary; transitions flip to 3 mid-chapter
    return 3


# ---------- mid-chapter regime transitions ----------------------------------


@dataclass
class RegimeSegment:
    """One contiguous segment of a chapter under a single regime.

    ``end_word_local`` is the chapter-local word offset at which this
    segment ends (exclusive); the final segment uses ``None`` to mean
    "to chapter end".
    """
    regime: int
    end_word_local: int | None  # chapter-local; None = to end of chapter


_TRANSITIONS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "manual" / "regime_transitions.json"
)


def load_regime_transitions(path: Path | None = None) -> list[dict]:
    """Load the configured mid-chapter regime transition list."""
    p = path or _TRANSITIONS_PATH
    if not p.exists():
        return []
    doc = json.loads(p.read_text())
    return list(doc.get("transitions") or [])


def _transition_word_local(
    transition: dict,
    perks_in_chapter: list[dict] | None,
    chapter_words: int,
) -> int | None:
    """Return the chapter-local word offset of a transition's trigger.

    For ``after_event.kind == "perk_acquired"`` we locate the matching
    perk in ``perks_in_chapter`` (a list of paid acquisitions in
    epub_sequence order) and use its position based on the standard
    even-spread convention used elsewhere in the simulator. The
    transition fires *immediately after* the perk's word offset, so the
    returned value is the end-of-segment word for the *prior* regime.
    """
    if not perks_in_chapter or chapter_words <= 0:
        return None
    after = transition.get("after_event") or {}
    kind = after.get("kind")
    if kind != "perk_acquired":
        return None
    needle = (after.get("perk_name") or "").strip().lower()
    if not needle:
        return None
    matches = [
        i for i, p in enumerate(perks_in_chapter)
        if (p.get("perk_name") or p.get("name") or "").strip().lower() == needle
    ]
    if not matches:
        return None
    idx = matches[0]
    n = len(perks_in_chapter)
    slot = chapter_words / n
    return int((idx + 0.5) * slot)


def regimes_for_chapter(
    chapter_num: str,
    transitions: list[dict] | None = None,
    perks_in_chapter: list[dict] | None = None,
    chapter_words: int = 0,
) -> list[RegimeSegment]:
    """Return an ordered list of ``RegimeSegment`` for one chapter.

    No transitions configured -> one segment with the chapter's primary
    regime. A configured transition splits the chapter at the
    transition's trigger word offset.
    """
    base = regime_for_chapter(chapter_num)
    if not transitions:
        return [RegimeSegment(regime=base, end_word_local=None)]
    applicable = [t for t in transitions if t.get("chapter_num") == chapter_num]
    if not applicable:
        return [RegimeSegment(regime=base, end_word_local=None)]
    # We support a single transition per chapter (the only documented
    # case so far). If multiple, we apply them in order.
    segments: list[RegimeSegment] = []
    current_regime = base
    for t in applicable:
        end_local = _transition_word_local(t, perks_in_chapter, chapter_words)
        if end_local is None:
            continue
        segments.append(RegimeSegment(
            regime=current_regime, end_word_local=end_local,
        ))
        current_regime = int(t["new_regime"])
    segments.append(RegimeSegment(regime=current_regime, end_word_local=None))
    if not segments:
        segments = [RegimeSegment(regime=base, end_word_local=None)]
    return segments


def shadow_words(perk_cost: int, regime: int) -> int:
    """Words of zero-CP-banking after a 600/800-CP perk in regime 3."""
    if regime != 3 or perk_cost not in (600, 800):
        return 0
    shadow_cp = int(perk_cost * SHADOW_CP_RATIO)
    return shadow_cp * REGIMES[3]["words_per_100_cp"] // 100


# ---------- shadow-aware CP accumulation ------------------------------------


@dataclass
class ShadowState:
    """Mutable state carried across simulator calls so shadows that
    extend past the chapter boundary continue to apply.
    """
    remaining: int = 0  # words of zero-CP-banking still active

    def copy(self) -> "ShadowState":
        return ShadowState(remaining=self.remaining)


def _accumulate_x100(
    elapsed_words: int,
    regime: int,
    banked_cp_x100_in: int,
    shadow_state: ShadowState,
) -> int:
    """Walk `elapsed_words` of text under `regime`, returning the new
    banked-CP*100 count. Shadow words are burned off first, then the
    remaining words earn CP at the regime rate. Mutates `shadow_state`.
    """
    if elapsed_words <= 0:
        return banked_cp_x100_in
    if shadow_state.remaining > 0:
        consumed = min(shadow_state.remaining, elapsed_words)
        shadow_state.remaining -= consumed
        elapsed_words -= consumed
    if elapsed_words <= 0:
        return banked_cp_x100_in
    words_per_100 = REGIMES[regime]["words_per_100_cp"]
    # 100 * (elapsed_words * 100 / words_per_100), floor div for stability.
    cp_x100 = elapsed_words * 10000 // words_per_100
    return banked_cp_x100_in + cp_x100


def accumulate_cp(
    words: int,
    regime: int,
    banked_cp_in: int,
    shadow_state: ShadowState | None = None,
) -> tuple[int, ShadowState]:
    """Pure word-to-CP arithmetic for `words` words at `regime`, starting
    from `banked_cp_in` banked CP and an optional `shadow_state`.

    Returns `(banked_cp_out, new_shadow_state)`. The output shadow state
    is a fresh copy; the input is left untouched.
    """
    state = (shadow_state or ShadowState()).copy()
    banked_x100 = _accumulate_x100(words, regime, banked_cp_in * 100, state)
    return banked_x100 // 100, state


# ---------- whole-story event walk (used by predict_rolls.py) ---------------


@dataclass
class Event:
    """An event consumed by the whole-story simulator."""
    word: int                   # cumulative word offset of this event
    kind: str                   # "chapter_start" | "acquisition" | "regime_change"
    chapter_num: str
    perk_cost: int = 0          # for acquisitions: total CP debited
    perk_principal_cost: int = 0  # for acquisitions: largest single-perk cost (shadow trigger)


@dataclass
class PredictedRoll:
    roll_number: int
    word_position: int
    chapter_num: str
    cp_rule_regime: int
    roll_trigger_cp_threshold: int


def simulate_story(
    chapters_in_order: list[dict],
    paid_by_chapter: dict[str, list[dict]],
    exact_words: dict[str, int],
    transitions: list[dict] | None = None,
) -> tuple[list[PredictedRoll], dict[str, int], dict[str, int], int]:
    """Whole-story simulation. Walks chapter starts and paid acquisitions
    in word order, accumulating CP and firing rolls when the regime's
    threshold is reached.

    Mid-chapter regime transitions (see ``regimes_for_chapter``) inject
    additional ``regime_change`` events at the transition word offsets.

    Returns ``(predicted_rolls, chapter_word_start, chapter_word_end,
    total_words)``.
    """
    events: list[Event] = []
    cumulative = 0
    chapter_word_start: dict[str, int] = {}
    chapter_word_end: dict[str, int] = {}

    for c in chapters_in_order:
        cn = c["chapter_num"]
        chapter_word_start[cn] = cumulative
        events.append(Event(word=cumulative, kind="chapter_start", chapter_num=cn))
        words = exact_words[c["full_title"]]
        chap_acqs = paid_by_chapter.get(cn, [])
        if chap_acqs:
            slot = words / len(chap_acqs)
            for i, a in enumerate(chap_acqs):
                offset_in_chap = (i + 0.5) * slot
                events.append(Event(
                    word=cumulative + int(offset_in_chap),
                    kind="acquisition",
                    chapter_num=cn,
                    perk_cost=a["cost"],
                    perk_principal_cost=int(
                        a.get("principal_cost", a["cost"]) or a["cost"]
                    ),
                ))
        # Inject mid-chapter regime-change events.
        if transitions:
            segs = regimes_for_chapter(cn, transitions, chap_acqs, words)
            for seg in segs[:-1]:
                if seg.end_word_local is None:
                    continue
                events.append(Event(
                    word=cumulative + int(seg.end_word_local),
                    kind="regime_change",
                    chapter_num=cn,
                    perk_cost=0,
                ))
        cumulative += words
        chapter_word_end[cn] = cumulative
    total_words = cumulative

    # chapter_start at a position must come BEFORE acquisitions in
    # that chapter (which share or follow that word offset).
    def _kind_order(k: str) -> int:
        return {"chapter_start": 0, "regime_change": 1, "acquisition": 2}.get(k, 3)
    events.sort(key=lambda e: (e.word, _kind_order(e.kind)))

    predicted: list[PredictedRoll] = []
    banked_cp_x100 = 0
    shadow = ShadowState()
    if not chapters_in_order:
        return predicted, chapter_word_start, chapter_word_end, total_words

    current_chapter = chapters_in_order[0]["chapter_num"]
    current_regime = regime_for_chapter(current_chapter)
    last_word = 0

    def advance_to(target_word: int) -> None:
        """Walk from ``last_word`` to ``target_word`` accumulating CP and
        firing rolls at the *exact* word offset where banked CP crosses
        each regime threshold. Shadow words are burned first.
        """
        nonlocal banked_cp_x100, last_word
        if target_word <= last_word:
            return
        elapsed = target_word - last_word
        # Burn shadow first — no CP earned during shadow words.
        if shadow.remaining > 0:
            burn = min(shadow.remaining, elapsed)
            shadow.remaining -= burn
            last_word += burn
            elapsed -= burn
        if elapsed <= 0:
            last_word = target_word
            return
        rate_words = REGIMES[current_regime]["words_per_100_cp"]
        threshold_x100 = REGIMES[current_regime]["cp_per_roll"] * 100
        while elapsed > 0:
            deficit_x100 = threshold_x100 - banked_cp_x100
            if deficit_x100 <= 0:
                # Already at/over threshold — fire at last_word.
                predicted.append(PredictedRoll(
                    roll_number=len(predicted) + 1,
                    word_position=last_word,
                    chapter_num=current_chapter,
                    cp_rule_regime=current_regime,
                    roll_trigger_cp_threshold=REGIMES[current_regime]["cp_per_roll"],
                ))
                banked_cp_x100 -= threshold_x100
                continue
            # words_to_threshold = ceil(deficit_x100 * rate_words / 10000)
            words_to_threshold = (deficit_x100 * rate_words + 9999) // 10000
            if words_to_threshold > elapsed:
                # Won't reach threshold this window; accumulate the rest.
                banked_cp_x100 += elapsed * 10000 // rate_words
                last_word += elapsed
                elapsed = 0
                break
            banked_cp_x100 += words_to_threshold * 10000 // rate_words
            last_word += words_to_threshold
            elapsed -= words_to_threshold
            if banked_cp_x100 >= threshold_x100:
                predicted.append(PredictedRoll(
                    roll_number=len(predicted) + 1,
                    word_position=last_word,
                    chapter_num=current_chapter,
                    cp_rule_regime=current_regime,
                    roll_trigger_cp_threshold=REGIMES[current_regime]["cp_per_roll"],
                ))
                banked_cp_x100 -= threshold_x100
        last_word = target_word

    # Per-chapter regime transition state: when entering a chapter, set
    # current_regime to the FIRST segment's regime (which may differ
    # from the chapter's primary regime if a transition starts at word 0).
    transitions_by_chapter: dict[str, list[RegimeSegment]] = {}
    if transitions:
        for c in chapters_in_order:
            cn = c["chapter_num"]
            words = exact_words.get(c["full_title"], 0)
            segs = regimes_for_chapter(
                cn, transitions, paid_by_chapter.get(cn, []), words,
            )
            transitions_by_chapter[cn] = segs

    pending_segments: dict[str, list[RegimeSegment]] = {
        cn: list(segs) for cn, segs in transitions_by_chapter.items()
    }

    for event in events:
        advance_to(event.word)

        if event.kind == "chapter_start":
            current_chapter = event.chapter_num
            segs = pending_segments.get(current_chapter)
            if segs:
                current_regime = segs[0].regime
                # Pop segment 0 only when its end is reached; keep it for
                # the regime_change handler.
            else:
                current_regime = regime_for_chapter(current_chapter)
        elif event.kind == "regime_change":
            segs = pending_segments.get(event.chapter_num) or []
            if segs:
                segs.pop(0)  # drop the segment that just ended
                if segs:
                    current_regime = segs[0].regime
        elif event.kind == "acquisition":
            shadow_cost = event.perk_principal_cost or event.perk_cost
            sw = shadow_words(shadow_cost, current_regime)
            if sw:
                shadow.remaining += sw

    advance_to(total_words)
    return predicted, chapter_word_start, chapter_word_end, total_words


# ---------- per-chapter simulation (used by derive_roll_outcomes.py) --------


@dataclass
class ChapterRollSim:
    """Output of `simulate_chapter_rolls` for one slot."""
    roll_idx: int                 # 0-based slot index inside the chapter
    chapter_num: str
    word_position: int            # CHAPTER-LOCAL word offset
    available_cp_pre_debit: int   # banked CP just BEFORE this roll fires
    banked_cp_post_debit: int     # banked CP after this roll's hit (if any) is debited
    roll_trigger_cp_threshold: int  # 100 or 200


def simulate_chapter_rolls(
    chapter_facts: dict,
    regime: int,
    banked_cp_in: int,
    hits_in_chapter: list[dict],
    shadow_state: ShadowState | None = None,
    segments: list[RegimeSegment] | None = None,
) -> tuple[list[ChapterRollSim], int, ShadowState]:
    """Replay one chapter and stamp pre-debit available CP on every slot.

    `chapter_facts` describes the chapter's predicted slots:
        { "chapter_num": str,
          "words": int,                     # total CP-eligible words
          "predicted_rolls": [ {
              "word_position": int,         # CHAPTER-LOCAL offset
              "roll_trigger_cp_threshold": int,  # 100 or 200
              "cp_rule_regime": int,        # informative; falls back to `regime`
          } ] }

    `hits_in_chapter` is the in-order list of paid acquisitions in this
    chapter, each ``{"word_position": int, "cost": int}``. ``word_position``
    is CHAPTER-LOCAL; if absent, hits are spread evenly across the chapter
    using the same rule as the predict_rolls walk.

    Returns ``(slots, banked_cp_out, new_shadow_state)`` where slots is one
    ChapterRollSim per predicted slot in word_position order, banked_cp_out
    is the banked CP at chapter end (after debits and remaining
    accumulation), and new_shadow_state carries any shadow that extends
    past the chapter boundary.
    """
    state = (shadow_state or ShadowState()).copy()
    chapter_num = chapter_facts["chapter_num"]
    total_words = int(chapter_facts.get("words") or 0)

    # Build event list local to chapter (word_position is chapter-local).
    predicted = sorted(
        chapter_facts.get("predicted_rolls", []),
        key=lambda r: r["word_position"],
    )
    n_pred = len(predicted)

    # Hit positions: prefer explicit; otherwise even spread.
    if hits_in_chapter and total_words > 0:
        if all(h.get("word_position") is not None for h in hits_in_chapter):
            hits_local = sorted(
                ({"word": h["word_position"], "cost": int(h["cost"])}
                 for h in hits_in_chapter),
                key=lambda h: h["word"],
            )
        else:
            slot = total_words / len(hits_in_chapter)
            hits_local = [
                {"word": int((i + 0.5) * slot), "cost": int(h["cost"])}
                for i, h in enumerate(hits_in_chapter)
            ]
    else:
        hits_local = []

    # Merge events (predicted-roll firings + hit acquisitions + regime
    # segment boundaries). Sort so that, at equal word, the predicted
    # roll fires before any regime change which fires before the hit's
    # debit (the roll's pre-debit CP is the available CP for the hit).
    events: list[tuple[int, int, str, dict]] = []
    for i, r in enumerate(predicted):
        events.append((int(r["word_position"]), 0, "roll", r))
    for h in hits_local:
        events.append((int(h["word"]), 2, "hit", h))
    # Inject regime change events from segments. The provided ``regime``
    # is the starting (segment 0) regime; we transition at each segment's
    # end_word_local to the NEXT segment's regime.
    seg_list = list(segments or [RegimeSegment(regime=regime, end_word_local=None)])
    if seg_list:
        for i in range(len(seg_list) - 1):
            end_w = seg_list[i].end_word_local
            if end_w is None:
                continue
            events.append((
                int(end_w), 1, "regime_change",
                {"new_regime": seg_list[i + 1].regime},
            ))
    events.sort(key=lambda e: (e[0], e[1]))

    banked_x100 = banked_cp_in * 100
    last_word = 0
    slots_out: list[ChapterRollSim] = []
    pending_hit_cost: int | None = None
    roll_idx = 0
    current_regime = seg_list[0].regime if seg_list else regime

    for word_pos, _, kind, payload in events:
        elapsed = word_pos - last_word
        if elapsed > 0:
            banked_x100 = _accumulate_x100(elapsed, current_regime, banked_x100, state)
        last_word = word_pos
        if kind == "roll":
            available_pre = banked_x100 // 100
            roll_trigger_cp_threshold = int(
                payload.get("roll_trigger_cp_threshold")
                or REGIMES[current_regime]["cp_per_roll"]
            )
            # NOTE: misses do NOT debit (curator semantics — banked CP
            # carries forward). Hits debit `cost`; the debit happens via
            # the "hit" event below.
            slots_out.append(ChapterRollSim(
                roll_idx=roll_idx,
                chapter_num=chapter_num,
                word_position=word_pos,
                available_cp_pre_debit=available_pre,
                banked_cp_post_debit=banked_x100 // 100,
                roll_trigger_cp_threshold=roll_trigger_cp_threshold,
            ))
            roll_idx += 1
        elif kind == "regime_change":
            current_regime = int(payload["new_regime"])
        elif kind == "hit":
            cost = int(payload["cost"])
            banked_x100 -= cost * 100
            if banked_x100 < 0:
                banked_x100 = 0
            sw = shadow_words(cost, current_regime)
            if sw:
                state.remaining += sw

    # Walk to end of chapter to drain remaining elapsed words.
    if total_words > last_word:
        banked_x100 = _accumulate_x100(
            total_words - last_word, current_regime, banked_x100, state,
        )

    return slots_out, banked_x100 // 100, state
