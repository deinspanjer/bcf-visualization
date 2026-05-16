"""Stage-1 regex scan for in-prose narrative references to rolls.

The regime simulation in `predict_rolls.py` predicts where each roll
should fire by word offset. To validate those predictions (especially
in chapters 76+ where the curator's roll log stops), we want to surface
actual narrative references in the chapter prose: the protagonist
narrating a roll attempt, a miss, an acquisition, or a constellation
reveal.

This script is **Stage 1**: pure regex over MC-POV prose. It is
deliberately liberal — false positives are acceptable here because a
later Stage-2 LLM pass will filter them. We just need to make sure that
every real roll event has at least one candidate nearby.

Inputs:
  - data/raw/Brocktons_Celestial_Forge.epub (chapter HTML at
    EPUB/chap_N.xhtml; index at EPUB/nav.xhtml)
  - data/derived/chapters.json
  - data/derived/chapter_sections.json
  - data/manual/section_classifications.json (the source of truth on
    which sections count as MC POV)

Output:
  - data/derived/roll_locations_regex.json (validated against
    data/derived/_schemas/roll_locations_regex.schema.json)

Design notes:

* Sections are walked using the same <p><strong>X</strong></p> marker
  splitter as `extract_chapter_sections.py`, so section indices line up
  with the existing `chapter_sections.json` and the manual
  classifications.
* Only sections whose `counts_for_cp` is True in
  `section_classifications.json` are scanned. This skips Preamble/
  Addendum/Interlude sections from non-Joe POVs, perk listings, news
  articles, PHO posts, meeting reports, and author notes.
* Regex scanning runs against the chapter HTML with tags replaced by
  spaces of equal length, so character offsets in the matched string
  line up with character offsets in the original chapter HTML. The
  `context` field is then derived by re-stripping the surrounding
  window into clean plain text and inserting `[[...]]` brackets around
  the matched phrase.
* `candidate_kind` is assigned by which regex group matched; if a
  region matches several patterns, the first matching kind wins
  (roll_attempt > miss > acquisition > constellation_reveal > general).
* Idempotent: re-running produces the same JSON.

This is pure stdlib (`zipfile`, `re`, `html.parser`).
"""

from __future__ import annotations

import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
CHAPTERS_JSON = ROOT / "data" / "derived" / "chapters.json"
SECTIONS_JSON = ROOT / "data" / "derived" / "chapter_sections.json"
CLASSIFICATIONS_JSON = ROOT / "data" / "manual" / "section_classifications.json"
OUT = ROOT / "data" / "derived" / "roll_locations_regex.json"


# ---------- HTML helpers ---------------------------------------------------

# The 14 constellations in the Celestial Forge catalog. Used to build a
# constellation-reveal regex that tolerates the bare constellation name
# being mentioned in narration.
KNOWN_CONSTELLATIONS = [
    "Alchemy", "Capstone", "Clothing", "Crafting", "Knowledge",
    "Magic", "Magitech", "Personal Reality", "Quality",
    "Resources and Durability", "Size", "Time", "Toolkits", "Vehicles",
]


def _strip_to_spaces(html: str) -> str:
    """Replace every HTML tag and HTML entity with spaces of equal
    length. Returns a string of the SAME length as the input where tag
    runs become whitespace runs. Plain-text characters keep their exact
    offsets.

    This is intentional: regex offsets in the result are valid offsets
    in the original chapter HTML, which is what the schema records.
    Entities like `&nbsp;` become e.g. 6 spaces, which is fine — they
    were that many characters in the HTML stream too.
    """
    out = list(html)
    for m in re.finditer(r"<[^>]*>", html):
        for i in range(m.start(), m.end()):
            out[i] = " "
    # Decode common entities by replacing them in place with spaces too;
    # entity references would otherwise leak into matches like &amp;.
    for m in re.finditer(r"&[a-zA-Z]+;|&#\d+;", html):
        for i in range(m.start(), m.end()):
            out[i] = " "
    return "".join(out)


class _PlainTextStripper(HTMLParser):
    """Collapses HTML to readable plain text, used only for the
    `context` field. Preserves paragraph breaks as single spaces.
    """

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _to_plain(html_fragment: str) -> str:
    s = _PlainTextStripper()
    s.feed(html_fragment)
    out = "".join(s.parts)
    out = re.sub(r"\s+", " ", out).strip()
    return out


# ---------- regex catalog --------------------------------------------------

# Every entry: (compiled_pattern, candidate_kind). When a position in
# the text matches multiple patterns we keep all matches but de-duplicate
# overlapping matches of the SAME phrase by (offset, length).

_CONSTELLATION_NAMES_RE = "|".join(
    re.escape(c) for c in sorted(KNOWN_CONSTELLATIONS, key=len, reverse=True)
)

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # ---- roll-attempt phrasings -------------------------------------
    (re.compile(r"\banother\s+(?:mote|connection)\b", re.IGNORECASE),
     "roll_attempt"),
    (re.compile(r"\b[Cc]elestial\s+[Ff]orge\s+(?:moved|advanced|swung|turned|shifted|spun|cycled|rotated)\b"),
     "roll_attempt"),
    (re.compile(r"\bfelt\s+the\s+[Cc]elestial\s+[Ff]orge\b"),
     "roll_attempt"),
    (re.compile(r"\bfelt\s+the\s+[Ff]orge\b"),
     "roll_attempt"),
    (re.compile(r"\b[Cc]onstellation\s+[Rr]evealed\b"),
     "roll_attempt"),
    # `passed` was originally bundled here, but reading the prose at ch
    # 20 ("the Magic constellation passed me by"), ch 50 (two Magic
    # misses both phrased "constellation passed by"), and ch 75 ("the
    # Alchemy constellation missed a connection") shows X-constellation-
    # passed is uniformly a MISS, not a roll attempt. Split out below.
    (re.compile(r"\b[Cc]onstellation\s+(?:pulled|swung|moved|advanced|approached)\b"),
     "roll_attempt"),
    (re.compile(r"\bmy\s+[Rr]each\b"),
     "roll_attempt"),
    (re.compile(r"\b[Rr]each\s+(?:grew|expanded|extended|grow|grows|growing)\b"),
     "roll_attempt"),
    (re.compile(r"\bfelt\s+my\s+power\s+(?:try|reach|latch|connect|extend|reaching|trying|latching)\b"),
     "roll_attempt"),
    # `connected` dropped from this verb list: "power connected" matched
    # ch100 prose about a Final Frontier ritual ("there had still been
    # power connected to that ceremony") that has nothing to do with the
    # gacha roll. The remaining verbs (reached/latched/grasped) are
    # tighter; the gacha-specific verb sense comes from the Forge anchor
    # patterns above ("felt the Forge", "the X constellation") rather
    # than from generic power-verb prose.
    (re.compile(r"\b(?:my\s+)?power\s+(?:reached|latched|grasped)\b"),
     "roll_attempt"),
    (re.compile(r"\bnext\s+(?:mote|connection|chance\s+(?:to|at))\b", re.IGNORECASE),
     "roll_attempt"),

    # ---- miss phrasings ---------------------------------------------
    (re.compile(r"\b(?:failed|tried)\s+to\s+(?:latch|connect|reach|grasp|secure|link)\b", re.IGNORECASE),
     "miss"),
    (re.compile(r"\bmissed\s+(?:a|the|that|another)\s+(?:mote|connection|constellation)\b", re.IGNORECASE),
     "miss"),
    # X constellation passed: see note above — uniformly a miss in the
    # curator log for ch 20 (Magic), ch 50 (Magic, twice), and the
    # general "X constellation passed by" idiom in MC POV.
    (re.compile(r"\b[Cc]onstellation\s+passed\b"),
     "miss"),
    # `wasn't enough` was dropped: 4/4 false positives in the manual
    # review (ch 5 'wasn't enough for me to compromise', ch 75 'wasn't
    # enough time', ch100 'wasn't enough to guarantee', 'wasn't enough
    # bandwidth'). The phrase is too common in non-gacha social/
    # logistical prose. Real misses are anchored on the Forge/
    # constellation patterns above and the failed/tried/missed verbs.
    (re.compile(r"\bspun\s+(?:away|out\s+of\s+reach|past)\b", re.IGNORECASE),
     "miss"),
    (re.compile(r"\b[Bb]anked\b"),
     "miss"),
    (re.compile(r"\bslipped\s+(?:away|past|out\s+of\s+reach)\b", re.IGNORECASE),
     "miss"),
    (re.compile(r"\bnot\s+enough\s+(?:to\s+(?:latch|connect|reach|grasp)|reach|power)\b", re.IGNORECASE),
     "miss"),

    # ---- acquisition phrasings --------------------------------------
    # `gained` dropped from this verb list: it triggers on capability-
    # growth recap prose ("New technologies were folded in as I gained
    # access to them" at ch100) that isn't a single roll event.
    # Real "I gained" usage in roll context is rare; the same events are
    # caught by 'I received' / 'I obtained' or by the Forge/constellation
    # anchors. Keeping obtained/received/acquired.
    (re.compile(r"\bI\s+(?:obtained|received|acquired)\b"),
     "acquisition"),
    (re.compile(r"\b(?:granted|gave)\s+me\s+(?:the\s+)?(?:perk|ability|power|knowledge|skill)\b", re.IGNORECASE),
     "acquisition"),
    (re.compile(r"\b[Mm]ote\s+(?:resolved|connected|locked|secured|settled|linked)\b"),
     "acquisition"),
    (re.compile(r"\bmemories\s+of\s+(?:the|that|another)\s+world\b", re.IGNORECASE),
     "acquisition"),
    (re.compile(r"\b(?:knowledge|memories)\s+(?:flooded|filled|poured\s+into)\s+(?:my|me)\b", re.IGNORECASE),
     "acquisition"),
    (re.compile(r"\bnew\s+(?:perk|power|ability)\s+(?:was|had)\b", re.IGNORECASE),
     "acquisition"),
    (re.compile(r"\blatched\s+on(?:to)?\s+(?:a|the|another)?\s*mote\b", re.IGNORECASE),
     "acquisition"),
    (re.compile(r"\bconnection\s+(?:solidified|formed|locked|made|completed|established)\b", re.IGNORECASE),
     "acquisition"),
    (re.compile(r"\b[Mm]ote\s+of\s+power\b"),
     "acquisition"),

    # ---- constellation reveals --------------------------------------
    # "the X Constellation" with X being a capitalized word-or-words
    (re.compile(r"\bthe\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+[Cc]onstellation\b"),
     "constellation_reveal"),
    # Bare known constellation name immediately preceding/following the
    # word "constellation" - case-sensitive on the constellation name
    # since these are proper nouns in the prose.
    (re.compile(rf"\b(?:{_CONSTELLATION_NAMES_RE})\s+[Cc]onstellation\b"),
     "constellation_reveal"),
    (re.compile(rf"\b[Cc]onstellation\s+(?:was|named|of)\s+['\"]?(?:{_CONSTELLATION_NAMES_RE})['\"]?\b"),
     "constellation_reveal"),
    # Quoted constellation announcement: '...was 'Quality' and...'
    (re.compile(rf"['\"](?:{_CONSTELLATION_NAMES_RE})['\"]"),
     "constellation_reveal"),

    # ---- general celestial-forge mentions in MC POV -----------------
    (re.compile(r"\b[Cc]elestial\s+[Ff]orge\b"),
     "general"),
    (re.compile(r"\b(?:my|the)\s+power\s+(?:tried|reached|extended|grew)\b", re.IGNORECASE),
     "general"),
]

# Kind precedence — when overlapping matches of different kinds cover
# the same character span, prefer the more specific kind.
_KIND_RANK = {
    "roll_attempt": 0,
    "miss": 1,
    "acquisition": 2,
    "constellation_reveal": 3,
    "general": 4,
}


# ---------- section splitter (matches extract_chapter_sections.py) ---------

_PLAIN_PAI_MARKER_RE = (
    r"(?:Preamble|Addendum|Interlude)[:\s]+[A-Z][A-Za-z0-9 .'\-]{0,60}"
)
_PLAIN_TITLE_PAI_MARKER_RE = (
    r"(?:\d+(?:\.\d+)?\s+)?" + _PLAIN_PAI_MARKER_RE
)
_PLAIN_SECTION_MARKER_RE = (
    r"(?:Jumpchain abilities this chapter:?|New abilities for [^:<]+:?|"
    + _PLAIN_TITLE_PAI_MARKER_RE
    + r")"
)

_MARKER_RE = re.compile(
    r"(?:"
    r"<p[^>]*>\s*(?:"
    r"<strong[^>]*>(?P<strong>[^<]+)</strong>"
    r"|(?P<plain>" + _PLAIN_SECTION_MARKER_RE + r")"
    r")\s*</p>"
    r"|<strong[^>]*>(?P<strong_inline>" + _PLAIN_SECTION_MARKER_RE + r")</strong>"
    r"|(?<=>)\s*(?P<plain_inline>" + _PLAIN_TITLE_PAI_MARKER_RE + r")\s*(?=<p\b)"
    r")",
    re.IGNORECASE,
)


def _marker_header(match: re.Match[str]) -> str:
    return (
        match.group("strong")
        or match.group("plain")
        or match.group("strong_inline")
        or match.group("plain_inline")
        or ""
    ).strip()


def _split_sections(html: str) -> list[tuple[str | None, int, int]]:
    """Return list of (header, html_start, html_end) tuples covering the
    full chapter HTML, identical to extract_chapter_sections._split_sections.
    """
    markers = list(_MARKER_RE.finditer(html))
    if not markers:
        return [(None, 0, len(html))]
    out: list[tuple[str | None, int, int]] = []
    if markers[0].start() > 0:
        out.append((None, 0, markers[0].start()))
    for i, m in enumerate(markers):
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(html)
        out.append((_marker_header(m), start, end))
    return out


def _build_chapter_index(zf: zipfile.ZipFile) -> dict[str, str]:
    """Map chapter full_title -> EPUB href, parsed from EPUB/nav.xhtml."""
    nav = zf.read("EPUB/nav.xhtml").decode("utf-8")
    out: dict[str, str] = {}
    for href, title in re.findall(
        r'<a[^>]*?href="([^"]+)"[^>]*>([^<]+)</a>', nav, re.DOTALL
    ):
        out[title.strip()] = href
    return out


# ---------- match collection ------------------------------------------------

CONTEXT_RADIUS = 200    # chars on each side of the match in the HTML window

# Window radius for collapsing nearby hits into a single "event" anchor.
# The manual review observed that one in-prose roll often spawns 2-4
# hits within a ~200-char window (e.g. "felt the Forge" + "the
# Knowledge constellation" + "I received" all describe the same roll).
# The events array gives downstream consumers a deduplicated view at
# the roll-event grain while still preserving every raw match in
# `locations` for transparency.
EVENT_CLUSTER_RADIUS = 200

# Anchor-kind precedence WHEN CLUSTERING into events. Prefer the most
# specific roll anchor: a named constellation pinpoints which roll fired,
# 'miss' marks a known failure, 'roll_attempt' marks the moment of the
# attempt, 'acquisition' is the result, 'general' is catch-all.
_CLUSTER_ANCHOR_RANK = {
    "constellation_reveal": 0,
    "miss": 1,
    "roll_attempt": 2,
    "acquisition": 3,
    "general": 4,
}


def _collect_matches(
    section_html: str, section_html_start: int,
) -> list[tuple[int, int, str, str]]:
    """Run all regexes against the section HTML (with tags spaced out
    so offsets are preserved). Returns a list of
    (chapter_html_offset, length, matched_text, candidate_kind) tuples,
    deduplicated so identical (offset, length) pairs collapse to the
    highest-precedence kind.
    """
    spaced = _strip_to_spaces(section_html)
    raw: list[tuple[int, int, str, str]] = []
    for pattern, kind in _PATTERNS:
        for m in pattern.finditer(spaced):
            phrase = m.group(0).strip()
            # Only keep if the match isn't pure whitespace (would mean
            # the regex matched across a tag with no real text).
            if not phrase:
                continue
            raw.append((m.start(), m.end(), phrase, kind))
    # Sort by start, then descending length (so longer overlapping
    # matches are considered first).
    raw.sort(key=lambda r: (r[0], -(r[1] - r[0])))

    # Greedy dedupe: when two matches' spans overlap (any character
    # shared), keep the one with the higher-precedence kind, breaking
    # ties by longer span. This collapses pairs like
    # 'the Knowledge constellation' (offset N, len 27) and 'Knowledge
    # constellation' (offset N+4, len 23) into a single candidate.
    kept: list[tuple[int, int, str, str]] = []
    for start, end, phrase, kind in raw:
        clobbered = False
        for i, (k_start, k_end, k_phrase, k_kind) in enumerate(kept):
            if end <= k_start or start >= k_end:
                continue   # disjoint
            # Overlap. Decide which to keep.
            cand_better = (
                _KIND_RANK[kind] < _KIND_RANK[k_kind]
                or (_KIND_RANK[kind] == _KIND_RANK[k_kind]
                    and (end - start) > (k_end - k_start))
            )
            if cand_better:
                kept[i] = (start, end, phrase, kind)
            clobbered = True
            break
        if not clobbered:
            kept.append((start, end, phrase, kind))

    results = [
        (section_html_start + s, e - s, p, k)
        for s, e, p, k in kept
    ]
    results.sort(key=lambda r: r[0])
    return results


def _cluster_to_events(section_locs: list[dict]) -> list[dict]:
    """Collapse a section's regex hits into roll-event clusters.

    Two adjacent (sorted by offset) hits join the same cluster when
    their offsets are within EVENT_CLUSTER_RADIUS chars. Within a
    cluster we keep every member's phrase/kind for downstream analysis,
    but elect a single "anchor" hit by _CLUSTER_ANCHOR_RANK so the
    event has one offset, one canonical kind, and one match_phrase.
    """
    if not section_locs:
        return []
    section_locs = sorted(section_locs, key=lambda l: l["match_offset"])
    clusters: list[list[dict]] = [[section_locs[0]]]
    for loc in section_locs[1:]:
        if loc["match_offset"] - clusters[-1][-1]["match_offset"] <= EVENT_CLUSTER_RADIUS:
            clusters[-1].append(loc)
        else:
            clusters.append([loc])
    out: list[dict] = []
    for cluster in clusters:
        anchor = min(
            cluster,
            key=lambda l: (_CLUSTER_ANCHOR_RANK[l["candidate_kind"]], l["match_offset"]),
        )
        kinds = sorted({l["candidate_kind"] for l in cluster})
        out.append({
            "chapter_num": anchor["chapter_num"],
            "epub_href": anchor["epub_href"],
            "section_index": anchor["section_index"],
            "anchor_kind": anchor["candidate_kind"],
            "anchor_phrase": anchor["match_phrase"],
            "anchor_offset": anchor["match_offset"],
            "kinds_present": kinds,
            "hit_count": len(cluster),
            "context": anchor["context"],
        })
    return out


def _build_context(
    chapter_html: str, match_offset: int, match_length: int,
) -> str:
    """Return a ~300-char plain-text context window with [[match]]
    bracketing the matched phrase.
    """
    radius = CONTEXT_RADIUS
    left_html = chapter_html[max(0, match_offset - radius): match_offset]
    matched_html = chapter_html[match_offset: match_offset + match_length]
    right_html = chapter_html[match_offset + match_length:
                              match_offset + match_length + radius]
    left = _to_plain(left_html)
    matched = _to_plain(matched_html)
    right = _to_plain(right_html)
    # If matched has no plain-text content (rare; would mean the match
    # overlapped a tag boundary) fall back to the matched-html stripped
    # of tags so the [[ ... ]] still wraps something useful.
    if not matched:
        matched = re.sub(r"<[^>]+>", "", matched_html).strip()
    return f"{left} [[{matched}]] {right}".strip()


# ---------- main ------------------------------------------------------------


def main() -> None:
    if not EPUB.exists():
        raise SystemExit(
            f"missing {EPUB.relative_to(ROOT)}; this script needs the source EPUB"
        )

    chapters = json.loads(CHAPTERS_JSON.read_text())["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))

    classifications = json.loads(CLASSIFICATIONS_JSON.read_text())["classifications"]

    # Validate against chapter_sections.json for parity (this script and
    # extract_chapter_sections.py must produce the same section ordering
    # so section_classifications.json keys align).
    sections_data = json.loads(SECTIONS_JSON.read_text())
    sections_by_chap = {c["chapter_num"]: c for c in sections_data["chapters"]}

    locations: list[dict] = []
    events: list[dict] = []
    by_chapter: dict[str, int] = {}
    by_kind: dict[str, int] = {}

    with zipfile.ZipFile(EPUB) as zf:
        title_to_href = _build_chapter_index(zf)
        for c in chapters:
            href = title_to_href.get(c["full_title"])
            if not href:
                continue
            html = zf.read(f"EPUB/{href}").decode("utf-8")
            sections_html = _split_sections(html)

            # Sanity-check that section count matches what
            # chapter_sections.json recorded; fail loudly if drift.
            recorded = sections_by_chap.get(c["chapter_num"])
            if recorded is not None and len(sections_html) != len(recorded["sections"]):
                raise SystemExit(
                    f"chapter {c['chapter_num']}: split produced "
                    f"{len(sections_html)} sections but chapter_sections.json "
                    f"has {len(recorded['sections'])}; section splitter drift "
                    f"would invalidate manual classifications. Re-run "
                    f"scripts/extract_chapter_sections.py if the EPUB changed."
                )

            for section_index, (header, s_start, s_end) in enumerate(sections_html):
                key = f"{c['chapter_num']}@{section_index}"
                cls = classifications.get(key)
                # Default-False for anything not in the manual classifier:
                # we'd rather miss a few candidates than scan non-MC POV
                # prose. (In practice all 432 sections are classified.)
                if not cls or not cls.get("counts_for_cp"):
                    continue
                section_html = html[s_start:s_end]
                matches = _collect_matches(section_html, s_start)
                section_locs: list[dict] = []
                for offset, length, phrase, kind in matches:
                    context = _build_context(html, offset, length)
                    loc = {
                        "chapter_num": c["chapter_num"],
                        "epub_href": href,
                        "section_index": section_index,
                        "match_phrase": phrase,
                        "match_offset": offset,
                        "context": context,
                        "candidate_kind": kind,
                    }
                    locations.append(loc)
                    section_locs.append(loc)
                    by_chapter[c["chapter_num"]] = by_chapter.get(c["chapter_num"], 0) + 1
                    by_kind[kind] = by_kind.get(kind, 0) + 1
                # Cluster within-section: hits whose offsets are within
                # EVENT_CLUSTER_RADIUS chars of the previous one in the
                # cluster collapse into a single event. The event's
                # anchor kind/phrase/offset is taken from the highest-
                # precedence kind in the cluster (see _CLUSTER_ANCHOR_RANK).
                events.extend(_cluster_to_events(section_locs))

    events_by_chapter: dict[str, int] = {}
    events_by_anchor_kind: dict[str, int] = {}
    for ev in events:
        events_by_chapter[ev["chapter_num"]] = events_by_chapter.get(ev["chapter_num"], 0) + 1
        events_by_anchor_kind[ev["anchor_kind"]] = events_by_anchor_kind.get(ev["anchor_kind"], 0) + 1

    payload = {
        "_source": (
            "Stage-1 regex scan of MC-POV sections in "
            "data/raw/Brocktons_Celestial_Forge.epub. MC sections are "
            "those with counts_for_cp=true in "
            "data/manual/section_classifications.json (i.e. excluding "
            "Preamble/Addendum/Interlude non-Joe POVs, perk listings, "
            "PHO posts, news articles, meeting reports, and author notes)."
        ),
        "_nuance_log": [
            "Reclassified 'X constellation passed' from roll_attempt to miss "
            "(uniformly a miss in the curator log for ch 20 / ch 50 — "
            "'the Magic constellation passed me by' = miss, not attempt).",
            "Dropped \"wasn't enough\" pattern (4/4 false positives in the manual "
            "review: matched social/logistical prose like 'wasn't enough time', "
            "'wasn't enough bandwidth'). Real misses are caught by other anchors.",
            "Dropped 'gained' from the 'I obtained|gained|received|acquired' "
            "verb list (ch 100 prose 'New technologies were folded in as I "
            "gained access to them' is capability-recap, not a single roll).",
            "Dropped 'connected' from the 'my power reached|latched|connected|"
            "grasped' verb list (ch 100 'power connected to that ceremony' "
            "matched a Final Frontier ritual, not a Forge connection).",
            "Added events array: hits within 200 chars of each other in the "
            "same section collapse to one event. Anchor kind precedence for "
            "clustering: constellation_reveal > miss > roll_attempt > "
            "acquisition > general (named constellation pinpoints the event "
            "more reliably than the generic verb anchors).",
        ],
        "_total_locations": len(locations),
        "_total_events": len(events),
        "_locations_by_chapter": dict(sorted(
            by_chapter.items(),
            key=lambda kv: (int(kv[0].split('.')[0]),
                            int(kv[0].split('.')[1]) if '.' in kv[0] else 0),
        )),
        "_locations_by_kind": dict(sorted(by_kind.items())),
        "_events_by_chapter": dict(sorted(
            events_by_chapter.items(),
            key=lambda kv: (int(kv[0].split('.')[0]),
                            int(kv[0].split('.')[1]) if '.' in kv[0] else 0),
        )),
        "_events_by_anchor_kind": dict(sorted(events_by_anchor_kind.items())),
        "_note": (
            "Stage-1 regex candidates for narrative roll references. "
            "Each entry tags an in-prose phrasing that LOOKS like the "
            "protagonist narrating a roll attempt, miss, acquisition, "
            "or constellation reveal. This pass is intentionally liberal "
            "and over-collects; expect false positives. Use these "
            "candidates as curator navigation hints and to validate "
            "predicted_rolls.json by checking "
            "that each predicted roll has at least one nearby narrative "
            "anchor; conversely, candidates with no nearby predicted "
            "roll may indicate the regime simulator is off. "
            "Interpretation key: candidate_kind = roll_attempt (the "
            "Forge moving / Joe's reach growing / felt the Forge / "
            "another mote), miss (failed-to-latch / missed mote / "
            "spun away / banked), acquisition (I obtained/gained/"
            "received / mote settled / memories of the world / new "
            "knowledge flooding in), constellation_reveal (a named "
            "constellation called out by the prose: 'the X "
            "Constellation' or 'the constellation was Y' or a quoted "
            "constellation name), general (catch-all Celestial Forge "
            "mention or vague power-reaching language; lowest "
            "confidence). When two patterns hit the same span, the more "
            "specific kind wins (precedence: roll_attempt > miss > "
            "acquisition > constellation_reveal > general). The "
            "match_offset is in the chapter HTML (not plain text); the "
            "context field is plain-text prose with [[match]] markers "
            "around the phrase that matched. The events array is the "
            "downstream-friendly view: one entry per ~200-char prose "
            "neighborhood of regex activity, with the highest-precedence "
            "match elected as the anchor. Use locations for fine-grained "
            "analysis, events for matching against curator rolls or "
            "predicted_rolls.json."
        ),
        "locations": locations,
        "events": events,
    }

    write_validated_json(OUT, payload, "roll_locations_regex")

    print(f"wrote {OUT.relative_to(ROOT)}: {len(locations)} candidates "
          f"across {len(by_chapter)} chapters; {len(events)} events")
    print(f"  by kind: {by_kind}")
    print(f"  by anchor kind (events): {events_by_anchor_kind}")
    if by_chapter:
        max_chap = max(by_chapter.items(), key=lambda kv: kv[1])
        min_chap = min(by_chapter.items(), key=lambda kv: kv[1])
        avg = len(locations) / len(by_chapter)
        print(f"  chapters with candidates: {len(by_chapter)} of {len(chapters)}")
        print(f"  per-chapter: min={min_chap[1]} (ch {min_chap[0]}), "
              f"max={max_chap[1]} (ch {max_chap[0]}), avg={avg:.1f}")


if __name__ == "__main__":
    main()
