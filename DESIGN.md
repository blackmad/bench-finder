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
  seal-preview:
    size: "56px"
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

A gallery's picture rail beside a map. The map stays on screen; next to it hang rows of photographs, each grouped by something true about the benches in view, and each photo is pinned with a small round compass seal when (and only when) the bench's facing is known. The rail opens straight onto the rows for what is in view. Clicking a bench (map marker or tile) opens it in the rail as a big photograph with a paper title card laid over its bottom edge, the map still beside it. A bench page is the same move at full bleed: the photo across the whole width, the title card over it, then the back of the postcard (stamp, facts, rating) beside a small map.

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
- **What the bench looks at leads; the compass is the detail.** When `faces_category` exists, copy says "Looks out over the water" (`looksAt()` in `data/facing.ts`) and the compass follows ("…, facing south"; tiles: "Looks out over the water · S 180°"). Without it, the compass sentence stands alone.
- **The rail never contradicts the map.** Whenever a photographed bench is in view it is in the first row, however few there are; the "No photographed benches…" note appears only when there are none.
- **Rows must come from fields the published data has** (`frontend/src/data/rows.ts`). The first row is always shown; a themed row with fewer than 3 photographed benches in view, or one that merely repeats the first row, is hidden. Current rows:
  - *Near the middle of the map* (*In view on the map* when fewer than 3): every photographed bench in view, nearest first (a bench picked on the map is moved to the front).
  - *Looks out over the water* / *the park*: by `faces_category` (appear once the data has it).
  - *On a gracht or kade*: street name ends in -gracht, -burgwal, -kade or -haven.
  - *In the parks*: street name ends in "park" (Science Park excluded: a business district).
  - *Along {street}*: the two streets with the most photographed benches in view (at least 4).
  - *Facing mapped* / *Facing estimated*: by `facing_method`.
  - *No backrest*: `backrest === false`.
  - Below the rows, *Not photographed yet*: a plain ruled list of the nearest 12 unphotographed benches.
- **Filters offer only what the data has** (`frontend/src/data/filters.ts`). A control appears once at least 3 benches carry its field; the rest are named in one "Not mapped yet" line, so a filter lights up by itself when the data arrives. Options no bench has are left out of multi-choice groups.
- **The hero photo is the sitter's view when we can tell.** `bench-finder publish` ranks each bench's images (`image_rank` in `bench_finder/publish/build.py`): a confirmed target detection first, then the camera behind the bench (trusted `view_relation` label, else camera bearing within 60° of the facing), then box size/centrality, confidence and recency. "More views" keep that order.
- Not available in the data, so not built: best-rated (ratings are per bench behind the Worker), most-photographed (gallery size is only in the per-bench files), neighbourhood names.

## Colors

Ink on card stock, one airmail blue for interaction and estimates, one vermilion for selection.

- **Airmail** (`airmail`): links, "See all", focus rings, checked ticks, search underline on focus; and the ink of estimated facings. `airmail-deep` for hover on the solid button; `airmail-wash` for result hover.
- **Vermilion** (`vermilion`): the selected bench only: tile outline, map thumb frame and pointer, map marker, the open bench's seal. `vermilion-ink` for small text (kickers, selected list item).
- **Card** (`card`): tiles, title cards, postback, top bar, map background. **Rail** (`card-rack`): page ground. **Stamp paper** (`stamp-paper`): seals, stamps, rose and marker hubs.
- **Ink / Ink 2 / Ink 3**: text at 17:1, 8.6:1 and 5.5:1 on card. **Rule**: hairlines.
- **Map water / park**: basemap re-ink (`frontend/src/map/style.ts`).

**The One Vermilion Rule.** Vermilion marks exactly one bench at a time and is never used for errors, hover or emphasis. The kicker labels ("Bench No. 1278 · Amsterdam") use `vermilion-ink` as print colour, the one exception, matching the approved mock.

**The Two Inks Rule.** Mapped facings in ink, estimated facings in airmail; blue never decorates.

## Typography

Archivo variable (wdth 62–125), self-hosted via `@fontsource-variable/archivo`.

- **Display** (800, clamp(40px, 4.4vw, 64px), lh 0.98, wdth 112, -0.015em, balanced): bench-page h1 on the title card; 36px on phone.
- **Hero title** (800, 40px; 30px phone): the address of the bench open in the rail.
- **Headline** (700, 22px, wdth 112): bench-page block heads over a 1.5px ink rule.
- **Lede** (400, 17px bench page / 15px rail preview, ink-2, max ~58ch).
- **Body** (400, 15px, lh 1.45, wdth 100).
- **Label caps** (700, wdth 125, uppercase, 0.04–0.05em): row titles 13px, tile captions 12px, kickers 11.5px, definition terms 11px, wordmark.
- **Meta** (12–13.5px, ink-2/ink-3): tile second line, row counts and notes, facts row.

**The Width-Axis Rule.** wdth 125 caps for printed labels, 112 for headlines, 100 for reading. **Tabular numerals** for counts, degrees, coordinates, ratings.

## Layout

**Atlas, desktop (above 760px).** 60px sticky top bar (wordmark, place search on an ink underline, sign-in). Below, a viewport-height grid: map 42fr | rail 58fr. The rail scrolls on its own (22px top, 32px gutters, 34px between blocks): the count line ("N benches in view on the map, M with a photo"), rows, the plain list. With a bench open (`?bench=ID`) the rail holds the preview instead.

**Atlas, phone (760px and below).** The map sits on top at 40vh (min 260px) and the rail flows below it with the page. Filters sits at the map's top-left, Near me at its top-right; the filters panel is a bottom sheet. An open bench takes the top of the rail, right under the map: photo edge to edge at 4:3.1 with the title card overlapping by 46px and inset 16px. Rows keep their sideways scroll with mandatory snap, tiles at 68vw, 16px gutters; row notes are hidden. Map zoom buttons are hidden (pinch), "Near me" stays.

**Bench page.** Full-bleed photo band (min(64vh, 600px); 54vh phone). Title card overlaps it by 150px (70px phone), max 720px wide: kicker, h1, lede, CTAs (Take me there = walking directions in Google Maps, Look around = jumps to the Street View block, Rate this bench = jumps to the rating). Then a 1280px sheet: postback (large stamp, definition list, rating and visited/favourite) beside a minimap (stacked under 900px); More views gallery (4-up, 2-up under 900px; captions "Looking SSW · 213° · Apr 2026", no badge on the photo); Street View; Nearby benches row (photographed, within 1 km, nearest first); Map data tags; Notes; Report.

## Elevation and depth

Flat paper with one lift. `--shadow-card` (0 1px 1px / 0 6px 18px -6px) on resting tiles, postback, minimap, gallery figures; `--shadow-card-lifted` (0 1px 1px / 0 14px 30px -10px) on title cards and hovered tiles (with translateY(-2px)). Seals and stamps use a small drop-shadow filter so they read as paper on photo. No glows, no blur, no glass.

## Components

### Tile (rail unit)
Card stock, 7px border, 4:3 photo cover-cropped low (50% 60%), seal at bottom-right of the photo, caption caps address (ellipsis), second line: "Looks out over the water · S 180°" when `faces_category` exists, else "Faces NE 52° · mapped · Backrest", "≈ Faces … · estimated" in airmail, or just the seat when the facing is unknown ("Seat not recorded" when neither). Hover or focus selects the bench (vermilion outline here and on the map) and lifts the tile. A plain click opens the bench in the rail preview; modified clicks keep the link to the bench page.

### Compass seal (signature)
A 38px round postmark-compass (56px on the rail preview): stamp-paper disc, 0.8px ink ring with 8 ticks, an N, and the needle rotated to the facing. Mapped: solid 2px ink shaft, filled head. Estimated: dashed 1.3px airmail shaft, open head. Selected: vermilion. `role="img"` with a full sentence label. Rendered only when a facing exists (`components/Seal.tsx`).

### Bench preview (rail)
Opened by a map marker or a tile; `?bench=ID` in the URL (pushes history, so Back returns to the rows). An airmail "‹ Benches in view" text button, then a 16:10 photo (4:3.1 phone) with the 56px seal top-right in vermilion; a paper title card overlaps the bottom edge by 64px, inset 22px, max 580px: vermilion-ink kicker "Bench No. N · City", address as the title, data-built lede, facts row (looks at, compass, seat, material), CTAs "Open the bench page" (solid) and "Take me there". Below, "More views" as a sideways strip of captioned figures. The map keeps the bench in vermilion.

### Rows
Caps title, ink-3 count ("266 in view") and note, "See all"/"See more" text button right (only when more than 12). The strip scrolls sideways with snap; "See all" turns it into a wrapping grid of up to 60.

### Filters
A "Filters" button at the map's top-left (card, shadow, inverts when open; an airmail count badge when any are on). It opens a 340px card popover over the map's left edge on desktop, non-modal so the map and rail update live behind it; on phones a modal bottom sheet (max 88dvh, backdrop, no blur). Head: caps "Filters" over a 1.5px ink rule and a close X. Foot: "N benches match" with "N in view" beneath, a Clear text button and a solid "Show N" that closes. Esc closes; focus returns to the button.
- **Looks at (leads).** The first group once `faces_category` has data: toggle chips (1px ink border, inverts when pressed) with counts, Water / Park / Square / Street / Playground / A wall / Something else. Until then it is named first in the "Not mapped yet" line.
- **Faces (compass), secondary.** A 184px postmark compass (200px phone): stamp-paper disc, ink ring with 16 ticks, eight wedges with ruled spokes. Each wedge holds an ink petal whose length is the sqrt of how many benches face that way (given the other filters), so the dial shows where the data is before anything is picked; the hub prints the count. The eight wind labels are round toggle buttons (`aria-pressed`, one tab stop, arrow keys move around the dial, Space/Enter toggles); the wedges are also click targets. Picked: ink-filled label, airmail-wash wedge, airmail petal. Under it "Facing SW or W" with an "Any direction" link, then "Facing known" (a Known / Mapped / ≈ Estimated strip once both kinds exist) and an ink-3 line with the coverage ("26 of 3,070 benches have a facing").
- **Yes/no fields** (backrest, lit): a strip of square radio cells, Any first, 1.5px ink frame, checked cell inverts to ink. **Multi-choice** (material, seats, kind of seat): the checkbox from the bench page in two columns. Every option carries its count in ink-3 tabular figures. Within a group options OR; groups AND.
- The rail and the map both use the filtered set; the count line becomes "12 of 1,685 benches in view: facing SW or W · backrest. Clear filters". The first row is kept even below 3 benches, filtered or not.
- URL keys: `photo=1`, `facing=known|mapped|estimated`, `dir=n,ne,…`, `back=yes|no`, `mat=wood,metal,…`, `lit=yes|no`, `seats=1-2,3,4,5+`, `faces=…`, `type=…`; written with replace, so filtering does not stack history.

### Stamp and postmark (bench page)
The Postcard Rack's perforated compass stamp (118×140, 96×114 on phone) in the postback; "No facing" when unknown, with no arrow and no postmark.

### Map
Re-inked positron basemap. Photographed benches are tiny postcards (58×42 photo, 3px card border) in one closed 1px ink frame that runs on into a small pointer whose tip is the bench (2px vermilion when selected); no facing badge on them. They cluster (52px radius, up to z19) instead of hiding each other: a collapsed marker shows its lowest-id member's photo with a second card peeking behind and an ink count pill at the top-right ("5"); clicking it zooms to where its benches separate. Every bench is always in some marker, photo or dot. Photos are fetched only for thumbnails on screen (`queryRenderedFeatures` on idle, then `triggerRepaint`), never in bulk. Unphotographed benches: a hub with a needle when the facing is known, a bare hub otherwise. Clusters: stamp-paper roses with a count and one tick per facing sector that the data really has. The minimap on the bench page shows one vermilion marker (needle only with a facing).

### Buttons
Square, 1.5px ink border, 700 weight. Default transparent with ink text, inverts on hover; solid = ink fill with card text, hover deep airmail. Text buttons (sign-in, "See all") have no border.

### Not photographed yet
A ruled list (auto-fill 210px columns): caps address, "No photo yet" or the facing beneath. The selected one turns vermilion-ink. Honest about the missing photo; no placeholder images.

### Icons
Inline SVG line icons, 24 grid, 18px, 1.6px stroke, round caps (search, user, pin, eye, star, flag, back).

### Motion
Tile lift 0.25s on `cubic-bezier(0.16, 1, 0.3, 1)`; the stamp strike-in when a stamp becomes selected. All switched off under `prefers-reduced-motion`.

## Do's and don'ts

**Do**
- Show a needle or seal only where `facing` exists; dashed airmail with "≈" when estimated.
- Build headlines and row titles from real fields with sober fallbacks (the address, the bench number).
- Hide a row with fewer than 3 benches rather than padding it.
- Keep the map usable without location permission; "Near me" asks only on press.
- Keep corners square; circles only for compass forms.

**Don't**
- Don't invent prose ("Looks out over the IJ") or categories the data lacks; "Looks out over the water" only from `faces_category`.
- Don't add a "bench of the day" or other editorial hero above the rows; the rail opens on what is in view.
- Don't put a legend line beside the count; the needle and seal explain themselves on hover and in labels.
- Don't use vermilion for anything but the selected bench (and the print-colour kickers).
- Don't fetch map thumbnails for unplaced features (r2.dev rate-limits).
- Don't use emoji as UI, glass, blur, gradient buttons, or show pipeline/debug data.

### Known limits
- Material, seats and lit reach the filters only through the GeoJSON, which `bench-finder publish` writes from this change on; the GeoJSON published on 2026-11-14 predates it, so those three controls stay hidden until the data is republished. `faces_category` and `bench_type` are still empty.
- Hero and bench-page photos are at most 800px wide in the published renditions, so the full-bleed bench-page band is upscaled on wide screens; a 1600w rendition would fix it.
- The Street View block keeps its large striped placeholder until opened.
