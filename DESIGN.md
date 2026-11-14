---
name: Bench Finder
description: A picture rail of benches beside the map; every photo carries a compass seal, and only where the facing is really known.
colors:
  card: "#f6f6f1"
  card-rack: "#ecece4"
  stamp-paper: "#fbfbf7"
  ink: "#141414"
  ink-2: "#4a4a46"
  ink-3: "#64645f"
  rule: "#d6d6cc"
  airmail: "#1e4fa3"
  airmail-deep: "#163d80"
  airmail-wash: "#dfe6f2"
  vermilion: "#e23b1e"
  vermilion-ink: "#cc3217"
  map-water: "#cfdbee"
  map-park: "#e6eadc"
  photo-empty: "#c9c9bf"
typography:
  display:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(40px, 4.4vw, 64px)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.015em"
    fontVariation: "'wdth' 112"
  hero-title:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.015em"
    fontVariation: "'wdth' 112"
  headline:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 112"
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontVariation: "'wdth' 100"
  lede:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.45
  label-caps:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    letterSpacing: "0.04em"
    fontVariation: "'wdth' 125"
  meta:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
rounded:
  none: "0px"
  focus: "2px"
  seal: "50%"
spacing:
  gutter: "32px"
  gutter-phone: "16px"
  tile-gap: "14px"
  row-gap: "34px"
  row-gap-phone: "28px"
  panel: "22px"
  section: "56px"
components:
  tile:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "7px 7px 10px"
    width: "236px"
  tile-phone:
    width: "68vw"
  title-card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "18px 22px"
  bench-title-card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.none}"
    padding: "22px 26px 24px"
  seal:
    backgroundColor: "{colors.stamp-paper}"
    rounded: "{rounded.seal}"
    size: "38px"
  seal-hero:
    size: "64px"
  stamp-large:
    width: "118px"
    height: "140px"
  button:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "11px 16px"
  button-solid:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.card}"
  top-bar:
    backgroundColor: "{colors.card}"
    height: "60px"
  top-bar-phone:
    height: "56px"
  map-thumb:
    backgroundColor: "{colors.card}"
    padding: "3px"
    width: "58px"
    height: "42px"
---

# Design System: Bench Finder

## Overview

**Creative North Star: "The Picture Rail"**

A gallery's picture rail beside a map. The map stays on screen; next to it hang rows of photographs, each grouped by something true about the benches in view, and each photo is pinned with a small round compass seal when (and only when) the bench's facing is known. A single "Bench of the day" leads the rail as a big photograph with a paper title card laid over its bottom edge. A bench page is the same move at full bleed: the photo across the whole width, the title card over it, then the back of the postcard (stamp, facts, rating) beside a small map.

It is the earlier Postcard Rack direction (paper, Archivo, the always-on re-inked map, needle markers, vermilion only for selection, the perforated compass stamp) crossed with the Title-Card Wall (hero with a headline on a paper card over the photo, horizontally scrolling rows by category, full-bleed bench pages). The approved reference mock is `frontend/design-reference/hybrid/` (its photos are not committed).

**Key characteristics:**
- Card stock (#f6f6f1) on a warmer rail ground (#ecece4); square corners everywhere except compass forms.
- The facing is the signature datum and it is never faked. Mapped facing = solid ink needle; estimated = dashed airmail needle with "≈"; no facing = no needle and no seal.
- Words come from data. Headlines are the street address (fallback "Bench No. N"); ledes are assembled from OSM tags, facing and photo date. No invented prose.
- Vermilion belongs to the one selected bench (tile outline, map thumb or marker).
- One typeface, Archivo, with the width axis as the hierarchy device.

## Honest-data rules

These are design rules, not just engineering ones; every surface follows them.

- **Seal and needle only where the facing exists.** `facingKind()` returns `mapped` (OSM `direction` tag or a visitor), `estimated` (model output, `facing_method` vlm/geometry) or null. Null draws nothing: tiles carry no seal, map dots are a bare hub (`m-none`), cluster roses grow no ticks for those benches (sector -1), the selected marker is a vermilion hub with no needle.
- **Rows must come from fields the published data has** (`frontend/src/data/rows.ts`). A row with fewer than 3 photographed benches in view is hidden. Current rows:
  - *Near the middle of the map*: every photographed bench in view, nearest first (a bench picked on the map is moved to the front).
  - *On a gracht or kade*: street name ends in -gracht, -burgwal, -kade or -haven.
  - *In the parks*: street name ends in "park" (Science Park excluded: a business district).
  - *Along {street}*: the two streets with the most photographed benches in view (at least 4).
  - *Facing mapped* / *Facing estimated*: by `facing_method`.
  - *No backrest*: `backrest === false`.
  - Below the rows, *Not photographed yet*: a plain ruled list of the nearest 12 unphotographed benches.
- **Bench of the day** is chosen deterministically per UTC day from photographed benches with a street address, preferring ones with a facing. Headline = address; lede from the bench JSON; facts = facing, seat, rating (only when the Worker reports at least one rating).
- Not available in the data, so not built: "faces the water/park" (`faces_category` is empty), best-rated (ratings are per bench behind the Worker), most-photographed (gallery size is only in the per-bench files), neighbourhood names.

## Colors

Ink on card stock, one airmail blue for interaction and estimates, one vermilion for selection.

- **Airmail** (`airmail`): links, "See all", focus rings, checked ticks, search underline on focus; and the ink of estimated facings. `airmail-deep` for hover on the solid button; `airmail-wash` for result hover.
- **Vermilion** (`vermilion`): the selected bench only: tile outline, map thumb frame and stem, map marker. `vermilion-ink` for small text (kickers, selected list item).
- **Card** (`card`): tiles, title cards, postback, top bar, map background. **Rail** (`card-rack`): page ground. **Stamp paper** (`stamp-paper`): seals, stamps, rose and marker hubs.
- **Ink / Ink 2 / Ink 3**: text at 17:1, 8.6:1 and 5.5:1 on card. **Rule**: hairlines.
- **Map water / park**: basemap re-ink (`frontend/src/map/style.ts`).

**The One Vermilion Rule.** Vermilion marks exactly one bench at a time and is never used for errors, hover or emphasis. The kicker labels ("Bench of the day", "Bench No. 1278 · Amsterdam") use `vermilion-ink` as print colour, the one exception, matching the approved mock.

**The Two Inks Rule.** Mapped facings in ink, estimated facings in airmail; blue never decorates.

## Typography

Archivo variable (wdth 62–125), self-hosted via `@fontsource-variable/archivo`.

- **Display** (800, clamp(40px, 4.4vw, 64px), lh 0.98, wdth 112, -0.015em, balanced): bench-page h1 on the title card; 36px on phone.
- **Hero title** (800, 40px; 30px phone): the Bench of the day address.
- **Headline** (700, 22px, wdth 112): bench-page block heads over a 1.5px ink rule.
- **Lede** (400, 17px bench page / 15px hero, ink-2, max ~58ch).
- **Body** (400, 15px, lh 1.45, wdth 100).
- **Label caps** (700, wdth 125, uppercase, 0.04–0.05em): row titles 13px, tile captions 12px, kickers 11.5px, definition terms 11px, wordmark.
- **Meta** (12–13.5px, ink-2/ink-3): tile second line, row counts and notes, facts row.

**The Width-Axis Rule.** wdth 125 caps for printed labels, 112 for headlines, 100 for reading. **Tabular numerals** for counts, degrees, coordinates, ratings.

## Layout

**Atlas, desktop (above 760px).** 60px sticky top bar (wordmark, place search on an ink underline, sign-in). Below, a viewport-height grid: map 42fr | rail 58fr. The rail scrolls on its own (22px top, 32px gutters, 34px between blocks): hero, count line with the needle key, rows, the plain list.

**Atlas, phone (760px and below).** The map sits on top at 40vh (min 260px) and the rail flows below it with the page. The hero photo goes edge to edge at 4:3.1 with the title card overlapping by 46px and inset 16px. Rows keep their sideways scroll with mandatory snap, tiles at 68vw, 16px gutters; row notes are hidden. Map zoom buttons are hidden (pinch), "Near me" stays.

**Bench page.** Full-bleed photo band (min(64vh, 600px); 54vh phone). Title card overlaps it by 150px (70px phone), max 720px wide: kicker, h1, lede, CTAs (Take me there = walking directions in Google Maps, Look around = jumps to the Street View block, Rate this bench = jumps to the rating). Then a 1280px sheet: postback (large stamp, definition list, rating and visited/favourite) beside a minimap (stacked under 900px); More views gallery (4-up, 2-up under 900px); Street View; Nearby benches row (photographed, within 1 km, nearest first); Map data tags; Notes; Report.

## Elevation and depth

Flat paper with one lift. `--shadow-card` (0 1px 1px / 0 6px 18px -6px) on resting tiles, postback, minimap, gallery figures; `--shadow-card-lifted` (0 1px 1px / 0 14px 30px -10px) on title cards and hovered tiles (with translateY(-2px)). Seals and stamps use a small drop-shadow filter so they read as paper on photo. No glows, no blur, no glass.

## Components

### Tile (rail unit)
Card stock, 7px border, 4:3 photo cover-cropped low (50% 60%), seal at bottom-right of the photo, caption caps address (ellipsis), second line: "Faces NE 52° · mapped · Backrest", "≈ Faces … · estimated" in airmail, or just the seat when the facing is unknown ("Seat not recorded" when neither). Hover or focus selects the bench (vermilion outline here and on the map) and lifts the tile.

### Compass seal (signature)
A 38px round postmark-compass (64px on the hero): stamp-paper disc, 0.8px ink ring with 8 ticks, an N, and the needle rotated to the facing. Mapped: solid 2px ink shaft, filled head. Estimated: dashed 1.3px airmail shaft, open head. Selected: vermilion. `role="img"` with a full sentence label. Rendered only when a facing exists (`components/Seal.tsx`).

### Bench of the day (hero)
16:7.4 photo (4:3.1 phone) with the 64px seal top-right; a paper title card overlaps the bottom edge by 64px, inset 22px, max 580px: vermilion-ink kicker, address as the title, data-built lede, facts row. The whole thing is one link to the bench page; hover zooms the photo 2% and underlines the title.

### Rows
Caps title, ink-3 count ("266 in view") and note, "See all"/"See more" text button right (only when more than 12). The strip scrolls sideways with snap; "See all" turns it into a wrapping grid of up to 60.

### Stamp and postmark (bench page)
The Postcard Rack's perforated compass stamp (118×140, 96×114 on phone) in the postback; "No facing" when unknown, with no arrow and no postmark.

### Map
Re-inked positron basemap. Photographed benches are tiny postcards on stems (58×42 photo, 3px border) with a needle badge only when the facing is known; photos are fetched only for thumbnails MapLibre actually placed (`queryRenderedFeatures` on idle, then `triggerRepaint`), never in bulk. Unphotographed benches: a hub with a needle when the facing is known, a bare hub otherwise. Clusters: stamp-paper roses with a count and one tick per facing sector that the data really has. The minimap on the bench page shows one vermilion marker (needle only with a facing).

### Buttons
Square, 1.5px ink border, 700 weight. Default transparent with ink text, inverts on hover; solid = ink fill with card text, hover deep airmail. Text buttons (sign-in, "See all") have no border.

### Not photographed yet
A ruled list (auto-fill 210px columns): caps address, "No photo yet" or the facing beneath. The selected one turns vermilion-ink. Honest about the missing photo; no placeholder images.

### Icons
Inline SVG line icons, 24 grid, 18px, 1.6px stroke, round caps (search, user, pin, eye, star, flag, back).

### Motion
Tile lift 0.25s and hero photo zoom 0.6s on `cubic-bezier(0.16, 1, 0.3, 1)`; the stamp strike-in when a stamp becomes selected. All switched off under `prefers-reduced-motion`.

## Do's and don'ts

**Do**
- Show a needle or seal only where `facing` exists; dashed airmail with "≈" when estimated.
- Build headlines and row titles from real fields with sober fallbacks (the address, the bench number).
- Hide a row with fewer than 3 benches rather than padding it.
- Keep the map usable without location permission; "Near me" asks only on press.
- Keep corners square; circles only for compass forms.

**Don't**
- Don't invent prose ("Looks out over the IJ") or categories the data lacks.
- Don't use vermilion for anything but the selected bench (and the print-colour kickers).
- Don't fetch map thumbnails for unplaced features (r2.dev rate-limits).
- Don't use emoji as UI, glass, blur, gradient buttons, or show pipeline/debug data.

### Known limits
- Hero and bench-page photos are at most 800px wide in the published renditions, so the full-bleed bench-page band is upscaled on wide screens; a 1600w rendition would fix it.
- The Street View block keeps its large striped placeholder until opened.
