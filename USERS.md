# Using the visualization

This project ships a static, dependency-free web visualization for
*Brockton's Celestial Forge*. It reads committed derived JSON and does
not require the raw EPUB or spreadsheets at runtime.

## Run locally

From the repository root:

```sh
python3 -m http.server 8001
```

Open <http://127.0.0.1:8001/web/>. The root page redirects to
`/web/`, but the explicit URL is useful while developing.

## Scrubber controls

- **Horizontal scroll** moves the visible window across the story.
- **Zoom** changes the width of the word-axis timeline. The default is
  zoomed in enough for roll dots to separate visually.
- **Play/Pause** replays progression at the selected speed. The default
  speed is `10k w/s`.
- **Reset** clears the saved word bookmark and returns to the pre-roll
  lead-in.
- **Keyboard** on the playhead supports arrows, PageUp/PageDown, Home,
  and End.

While playing, the playhead naturally stays centered except near the
beginning and end of the scroll range. If you manually scroll while
paused, the visualization stays where you put it. If you manually
scroll while playing, it holds that scroll position for three seconds
and then gradually catches back up to the natural centered position.
Starting playback from the end jumps back to the beginning before
replaying.

## Reading the tracks

- **Real date**: publish-date ticks. More detail appears as zoom
  increases.
- **Chapters**: chapter boundaries and major chapter labels. Click a
  chapter tick to open the selected-chapter detail panel.
- **POV / sections**: section spans. Color distinguishes section POV;
  pale spans do not earn CP under the current classifier.
- **Recovery**: cooldown shadows after expensive perks.
- **Rolls**: hit/acquisition dots on the upper lane; misses and
  unknowns on the lower lane. Dot color is constellation, dot size is
  purchased perk cost, dashed border means narrated/untracked
  acquisition, and tiny child dots below a purchase are free perks
  bundled with that purchase.
- **Words**: total word-position axis.

The legend panel repeats these encodings and can be collapsed.

## Forge Curator TUI

Launch the curator from the repository root with:

```sh
.venv/bin/python -m scripts.forge_curator --chapter 2
```

The left stats panel's Rolls heading reports predicted slots for the
current chapter. When a prior chapter's mechanical roll is narrated or
listed in the current chapter, the heading adds a deferred count, for
example `4 predicted +1 deferred`.

Deferred rolls appear at the top of the Rolls list before the current
chapter's `#1` roll. Their row names the mechanical source chapter and
roll index, and shows the CP that was available at the original roll
slot. Roll actions such as hit/miss, quote evidence, constellation, and
perk selection target that original mechanical roll while still letting
you work from the chapter where the evidence appears.

The Evidence list marks the saved quote under the prose cursor with
`▸`, matching the selected-roll marker used in the Rolls list.

## Persistence

The page stores the current word position, zoom, and playback speed in
`localStorage`. Use `reset` to clear the saved position. Browser
storage versions are bumped when incompatible defaults change.

## Data note

The scrubber is backed by `data/derived/chapter_facts.json`. Raw
copyrighted prose is not needed to view the site.

An experimental overhead sky prototype is parked at `/web/?sky=1`.
It is not the primary UI, but remains available for planetarium design
iteration.
