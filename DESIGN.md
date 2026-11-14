---
name: Bench Finder
description: Every bench is a picture postcard of its own view, postmarked with the direction it faces.
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
    fontSize: "clamp(30px, 3.1vw, 42px)"
    fontWeight: 750
    lineHeight: 1.02
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
    fontSize: "16.5px"
    fontWeight: 400
    lineHeight: 1.45
  label-caps:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 700
    letterSpacing: "0.04em"
    fontVariation: "'wdth' 125"
  serial:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    letterSpacing: "0.02em"
    fontFeature: "'tnum' 1"
    fontVariation: "'wdth' 112"
  meta:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
rounded:
  none: "0px"
  focus: "2px"
  pin: "50%"
spacing:
  card-border-phone: "6px"
  card-border: "9px"
  card-border-lg: "14px"
  gutter: "20px"
  rack-gap: "22px"
  panel: "28px"
  section: "56px"
components:
  postcard:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "9px 9px 0"
  postcard-phone:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.none}"
    padding: "6px 6px 0"
    width: "76vw"
  postcard-front-lg:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.none}"
    padding: "14px 14px 0"
  stamp:
    backgroundColor: "{colors.stamp-paper}"
    width: "74px"
    height: "88px"
  stamp-lg:
    backgroundColor: "{colors.stamp-paper}"
    width: "118px"
    height: "140px"
  stamp-phone:
    width: "50px"
    height: "60px"
  plain-row:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "10px 12px"
  button:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "9px 14px"
  button-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.card}"
  button-primary:
    backgroundColor: "{colors.airmail}"
    textColor: "#ffffff"
    rounded: "{rounded.none}"
    padding: "9px 14px"
  button-primary-hover:
    backgroundColor: "{colors.airmail-deep}"
  text-button:
    textColor: "{colors.ink}"
    padding: "8px 4px"
  text-button-hover:
    textColor: "{colors.airmail}"
  search-field:
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "6px 2px"
  checkbox:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.none}"
    size: "15px"
  facing-dial:
    size: "92px"
  facing-dial-sector-on:
    backgroundColor: "{colors.airmail}"
    textColor: "{colors.card}"
  facing-dial-sector-hover:
    backgroundColor: "{colors.airmail-wash}"
  top-bar:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    height: "60px"
    padding: "0 20px"
  top-bar-phone:
    height: "56px"
    padding: "0 14px"
  map-thumb:
    backgroundColor: "{colors.card}"
    padding: "3px"
    width: "58px"
    height: "42px"
---

# Design System: Bench Finder

## Overview

**Creative North Star: "The Postcard Rack"**

Every bench is a picture postcard of its own view, postmarked with the direction it faces. The interface is a spinning rack of white card stock beside a map: photos sit inside a printed white border, a perforated postage stamp in the corner prints a compass, and a postmark ring cancels the stamp along the bench's heading. The postal marks are never decoration. Each one carries the facing, and the stroke weight of that mark says whether the facing is known or estimated.

The world is light, matte and printed. Surfaces are flat paper on a slightly darker rack; depth comes only from the soft shadow of a card lifted off that rack. Colour is ink on card with one working blue (airmail) for interaction and estimated data, and one vermilion that belongs to exactly one bench at a time. Type is a single family, Archivo, used on its width axis: expanded bold caps are the printed caption and serial voice; normal-width text does the reading.

Density is calm on the rack (one postcard column, generous gaps) and dense on the map. The map is a basemap re-inked into the same card stock and airmail water, so the markers read as print on the same paper.

**Key Characteristics:**
- White card stock (#f6f6f1) cards on a warmer rack ground (#ecece4); square corners everywhere.
- Facing is the data every postal mark encodes: stamp compass, postmark cancel bars, map needle, cluster rose.
- Known facing = solid ink stroke; estimated facing = hairline dashed stroke, airmail blue, prefixed with "≈".
- Vermilion is reserved for the single selected bench.
- One typeface, Archivo, with the width axis (wdth 100 / 112 / 125) as the hierarchy device.
- One signature motion: the stamp "strikes" onto the selected card.

## Colors

Ink on white card stock, one airmail blue for interaction and estimates, one vermilion reserved for selection.

### Primary
- **Airmail Blue** (`airmail`): every interactive affordance (links, focus ring, primary button, checked checkbox tick, pressed dial sector, search underline on focus, text-button hover, text selection) and the ink of estimated facings on stamps, plain rows and map markers. Also the confidence meter fill.
- **Deep Airmail** (`airmail-deep`): hover state of the primary button only.
- **Airmail Wash** (`airmail-wash`): hover fill of a facing-dial sector.

### Secondary
- **Postmark Vermilion** (`vermilion`): the one selected bench. Its 2px ring around the selected postcard and map thumbnail, the selected stamp's arrow, label and postmark, the selected map needle and stem, and the selected map marker. Small vermilion text (the selected stamp's facing label) uses the deeper `vermilion-ink` (5.0:1 on stamp paper); plain vermilion is 4.15:1 there, fine for marks but not for 8px text.

### Neutral
- **Card Stock** (`card`): every card face, the top bar, filters panel, map key, map background, buttons at rest.
- **Rack** (`card-rack`): the page ground behind cards (body, the rack column, the detail page).
- **Stamp Paper** (`stamp-paper`): the slightly brighter paper of stamps, cluster roses, marker hubs and mini compasses, so postal marks sit visibly on top of the card.
- **Ink** (`ink`): primary text, known-facing marks, 1.5px rules, button borders, checkbox boxes, all rose and marker strokes.
- **Ink 2** (`ink-2`): secondary text on card stock (8.6:1): meta lines, serials, field labels, block subtitles.
- **Ink 3** (`ink-3`): tertiary text and placeholders (5.5:1 on card, 5.0:1 on rack), address lines, idle stars, plain-row hover border.
- **Rule** (`rule`): 1px hairline dividers between bar, filters, rack and card back panels; dial sector outlines; meter track.
- **Map Water / Map Park** (`map-water`, `map-park`): the basemap re-ink. Basemap background becomes card stock, water fills become map-water, park/landuse fills become map-park, and label text is muted to a warm grey.
- **Empty Photo** (`photo-empty`): the photo well behind an image that has not loaded.

### Named Rules
**The One Vermilion Rule.** Vermilion marks exactly one bench at a time: the selected one, everywhere it appears (card, stamp, thumbnail, map marker). It is never used for errors, badges, hover, or emphasis.

**The Two Inks Rule.** Known facings are drawn in ink; estimated facings are drawn in airmail blue. Blue therefore means either "you can press this" or "this is our estimate"; it never decorates.

## Typography

**Display Font:** Archivo (variable, wdth 62–125, wght 100–900), falling back to ui-sans-serif, system-ui, sans-serif
**Body Font:** Archivo
**Label/Mono Font:** Archivo at expanded width with tabular numerals (no separate mono)

**Character:** One grotesque stretched and squeezed like postal print: expanded bold caps for the street name and labels read as a printed caption, slightly expanded semibold for headlines, normal width for reading.

### Hierarchy
- **Display** (750, clamp(30px, 3.1vw, 42px), line-height 1.02, wdth 112, -0.015em, balanced wrap): the detail page's headline, written as what the bench looks at ("Looks out over the water").
- **Headline** (700, 22px, wdth 112, -0.01em): detail page block headings ("The view from this bench", "More views", "Notes"), sitting on a 1.5px ink rule with a right-aligned ink-2 subtitle.
- **Lede** (400, 16.5px, ink-2, max 34ch): the one-sentence description under the display line.
- **Body** (400, 15px, line-height 1.45, wdth 100): all reading text, form labels, buttons (buttons and text buttons at 600).
- **Caption caps** (700, wdth 125, uppercase, 0.04em): street-name captions on postcards (12.5px rack, 11.5px phone and plain rows, 15px large front), field labels and filter group labels (11px), the wordmark (17px desktop, 15px phone), the address line "Bench No.".
- **Serial** (500, 12px, wdth 112, tabular numerals, 0.02em, ink-2): "No. 1472" serials.
- **Meta** (400, 12–12.5px, ink-2): card meta lines, map key, dial hint, gallery captions, coordinates.

### Named Rules
**The Width-Axis Rule.** Hierarchy is set by Archivo's width axis before size: wdth 125 caps for printed captions and labels, wdth 112 for headlines and serials, wdth 100 for reading. Do not introduce a second family.

**The Tabular Numbers Rule.** Serials, counts, degrees, coordinates and cluster counts always use tabular numerals.

## Layout

**Atlas (desktop, above 760px).** A 60px card-stock top bar (wordmark, place search with a 1.5px ink underline capped at 420px, sign-in text button), then a two-column grid: map on the left (1fr) and the rack on the right (minmax(440px, 40vw)), filling the viewport height. The rack stacks a filters panel on card stock (field groups left, the 92px facing dial right), a rack head (count plus the known/estimated key), and a scrolling single column of postcards with 22px gaps and 20px side gutters. Photographed benches come first, sorted by distance from map centre; unphotographed benches follow as compact plain rows (capped at 24) under a "Not yet photographed" caps label.

**Phone (760px and below).** The map fills the screen under a 56px bar. The rack becomes a horizontal, scroll-snapped stack of postcards docked at the bottom (each 76vw, centre-snapped, 12px gap, safe-area padding). The card snapped to centre is the selected bench. Filters, rack head and map key are hidden; a floating "Filters" chip (card stock, shadow) top-left opens the filters panel as a sheet from the top. The search collapses to its icon and expands across the bar on focus. Plain rows and card meta lines are dropped on phone; photo aspect tightens from 3:2 to 16:9.

**Detail page.** Centred 1240px container (36px/32px padding; 18px/16px under 900px). The postcard is shown as a spread: front (4:3 photo, large stamp) at 1.08fr beside the back at 1fr, 28px gap. The back splits into a message side (headline, lede, definition list, rating and personal checkboxes) and an address side (small stamp top-right, ruled address lines, coordinates). Below, blocks are separated by 56px: Street View embed (21:9, 4:3 on phone), a 4-up gallery (2-up on phone), notes. Under 900px everything stacks to one column and the message/address divider turns into a dashed rule.

**Spacing rhythm.** 20px gutters are the default edge; 9px is the printed card border (6px on phone, 14px on the large front); 22px between postcards; 28px inside panels; 56px between detail blocks.

## Elevation & Depth

Flat paper with one lift. Every card (postcard, card back, gallery figure, notes panel, map key, filters sheet, Filters chip) uses the same two-layer card shadow: a 1px contact line plus a soft drop. Hover lifts a postcard 2px and deepens the drop. Postal marks (stamps, roses, mini compasses) use a small drop-shadow filter so they read as paper laid on paper. There are no glows, no blur, no tinted shadows.

### Shadow Vocabulary
- **Card** (`box-shadow: 0 1px 1px rgb(20 20 20 / 0.06), 0 6px 18px -6px rgb(20 20 20 / 0.22)`): every resting card and floating panel, including MapLibre control groups.
- **Card lifted** (`box-shadow: 0 1px 1px rgb(20 20 20 / .06), 0 14px 30px -10px rgb(20 20 20 / .3)`): postcard hover, paired with translateY(-2px).
- **Map thumb** (`box-shadow: 0 1px 1px rgb(20 20 20 / .2), 0 4px 10px -3px rgb(20 20 20 / .35)`): tiny postcards on the map, darker to separate from the basemap.
- **Stamp** (`filter: drop-shadow(0 1px 1.5px rgb(20 20 20 / .28))`): perforated stamps.
- **Selection ring** (`box-shadow: 0 0 0 2px vermilion, <card>`): the selected postcard; the selected map thumb pairs the ring with a deeper drop.

### Named Rules
**The Paper-On-Paper Rule.** Depth means a sheet lying on another sheet: one soft card shadow, square edges, nothing floats higher than a lifted postcard.

## Shapes

Square corners throughout: cards, buttons, checkboxes, inputs, map control groups (forced to 0 radius), sheets. The only circles are compass and postmark forms: the stamp's compass ring, the postmark's double ring, the map needle hub, the cluster rose ring, the mini compass. The stamp's edge is perforated (a masked row of 2.4px holes at 7.4px pitch) with an inner 0.7px ink frame. Rules are 1px hairlines (rule colour) for structure and 1.5px ink for emphasis (search underline, block heading underline, button borders, checkbox boxes). Photo wells use fixed aspect ratios: 3:2 rack, 16:9 phone stack, 4:3 detail front, 1:1 gallery, 21:9 embed.

## Components

### Postcard (signature)
The rack's unit: a photo inside a printed white border, a caption beneath, a stamp overlapping the top-right corner.
- **Shape:** square, card stock, 9px border on three sides with the caption closing the bottom (6px on phone).
- **Photo:** 3:2 (16:9 on phone), cover-cropped low (object-position 50% 62%) so the bench and its view both show.
- **Caption:** street name in caption caps left, serial "No. 1472" right, ellipsis on overflow; meta line below ("Looks at the water · Backrest") in ink-2, hidden on phone.
- **States:** hover lifts 2px with the lifted shadow (0.45s ease-out); selected adds the 2px vermilion ring and re-strikes the stamp in vermilion. Hovering a postcard selects it; on phone the centre-snapped card is selected.
- **Large front (detail):** 14px border, 4:3 photo, 15px caption caps, large stamp.

### Stamp and Postmark (signature)
A perforated postage stamp (74×88; 118×140 large; 50×60 phone) on stamp paper, printed with a 16-tick compass ring, an N in expanded caps, and a facing arrow. Below the compass, the facing label: "ENE 70°" when known, "≈ ENE" when estimated. A postmark (double ring with arc text "≈ ENE · 70°", three wavy cancel bars and a small arrow, all rotated to the heading) overlaps the stamp's lower-left corner at 0.78 opacity.
- **Known:** solid ink arrow (2.2px shaft, filled head and hub), postmark at 0.95px solid.
- **Estimated:** airmail hairline arrow (1.1px, dashed shaft, open head), postmark at 0.6px dashed.
- **Selected:** arrow, label and postmark switch to vermilion and the stamp plays the stamp-in strike.
- **Accessibility:** each stamp is `role="img"` with a full sentence title ("Probably faces ENE (70°), estimated with 53% confidence").

### Map markers
- **Unphotographed bench:** a canvas-drawn hub with a facing needle, drawn north and rotated by the map to the heading. Known = ink, 2.2px solid needle, filled head, stamp-paper hub with 2px ink ring. Estimated = airmail, 1.4px dashed needle, open head. Selected = solid vermilion hub (larger) and needle, scaled 1.2.
- **Photographed bench (map thumb):** a tiny postcard (58×42 photo in a 3px card border, map-thumb shadow) on a 9px ink stem, with a 20px round needle badge at its bottom-right corner pointing the facing. Hover lifts 3px. Selected turns the ring, stem and needle vermilion. Thumbs always stack above cluster roses.
- **Cluster (postmark rose):** a stamp-paper ring (radius 13 / 16 / 19 by count tiers 20 and 100) with a 1.5px ink outer ring, a 0.7px inner ring, the count in Archivo 700 wdth 112 tabular, and up to eight 2px ink ticks radiating from the ring, one per facing sector, length proportional to that sector's share. Hover scales 1.08; click zooms in two levels.

### Facing dial (filter)
A 92px eight-sector ring (N, NE … NW) around a small ink compass hub. Sectors are hairline rule outlines with 8px expanded-caps labels; hover fills airmail-wash; pressed fills airmail with card-colour labels (multi-select, `aria-pressed`). A hint line below names the selection ("Facing N, NE" or "Any direction").

### Buttons
- **Shape:** square (0px), 1.5px border, 600 weight, 9px 14px, inline icon gap 8px.
- **Default:** card stock with ink border and ink text; hover inverts to ink fill with card text.
- **Primary:** airmail fill and border with white text; hover goes to deep airmail. Used for the single main action ("Look around").
- **Disabled:** card fill with ink-3 border and text (5.5:1), for both default and primary; no opacity fade.
- **Text button:** no border or fill, 600 weight, ink; hover turns airmail. Used for sign-in, back crumb.
- **Inline link action:** airmail, 1px underline offset 3px ("Report this card", "Open in OpenStreetMap").

### Inputs / Fields
- **Search:** no box. Text on a 1.5px ink underline; the underline turns airmail on focus-within. Placeholder in ink-3. A 18px stroked search icon leads.
- **Checkbox:** a 15px square with a 1.5px ink border on card stock; checked draws an airmail tick that scales in (0.25s ease-out). Focus-visible puts the airmail ring on the box.
- **Focus (global):** 2px airmail outline, 2px offset.

### Plain row (unphotographed bench)
A compact bordered row on card stock (1px rule border, ink-3 on hover): a 40px facing glyph (rule ring with an ink or dashed-airmail needle), street name in caption caps with "Faces / Probably faces ENE · no photo yet" beneath, serial right. Honest about the missing photo rather than faking one.

### Navigation
The top bar is card stock with a 1px rule underneath: wordmark in caption caps (no city: the data spans several), search, then a sign-in text button with a stroked user icon. On phone the "Sign in" label drops away, leaving icons (the button keeps an aria-label).

### Detail back
- **Definition list:** caption-caps 11px terms in ink-2, 14.5px values; the facing value names its source beneath (OSM tag, or "Estimated from street views" with a 64×4 airmail confidence meter and percentage).
- **Address side:** ruled lines (1px ink-3) reading Bench No. / street / postcode city / country, like the address half of a postcard.
- **Gallery figures:** small postcards (7px border, 1:1) with a 26px mini compass pointing the image heading; caption "Looking NE · 34°".

### Icons
Inline SVG line icons on a 24 grid, 18px, 1.6px stroke, round caps and joins, currentColor (search, user, sliders, back, flag, eye, star, pin, turn).

### Motion
- **Stamp-in** (0.55s, `cubic-bezier(0.16, 1, 0.3, 1)`): from scale 1.35, -10° and transparent, to 0.96 and 1° at 60%, then rest. Plays only when a stamp becomes the selected stamp.
- **Lifts:** postcard 0.45s, map thumb 0.35s, rose 0.3s, all on the same ease-out.
- **Reduced motion:** the stamp-in and postcard transition are switched off.

## Do's and Don'ts

### Do:
- **Do** make every postal mark carry the facing: stamp arrow, postmark cancel bars, map needle, rose ticks. A mark without data is decoration and does not belong.
- **Do** draw known facings in solid ink and estimated ones in dashed airmail hairline with "≈", in every place a facing appears.
- **Do** keep vermilion for the one selected bench, synced across card, stamp, thumb and marker.
- **Do** set hierarchy with Archivo's width axis: wdth 125 caps for captions and labels, 112 for headlines and serials, 100 for text.
- **Do** keep corners square and depth to the single card shadow (0 1px 1px rgb(20 20 20 / 0.06), 0 6px 18px -6px rgb(20 20 20 / 0.22)).
- **Do** re-ink the basemap into card stock, map-water and map-park so markers print on the same paper.
- **Do** give every bench its "No." serial in tabular numerals.

### Don't:
- **Don't** use vermilion for errors, alerts, badges or hover.
- **Don't** round corners on cards, buttons, inputs or map controls; circles are reserved for compass and postmark forms.
- **Don't** add a second typeface or a system display face.
- **Don't** use emoji, glass or blur, or gradient buttons (owner-pinned).
- **Don't** show debug or pipeline data on bench surfaces; confidence appears only as the estimated-facing meter.
- **Don't** fake a photo for an unphotographed bench; use the plain row.

### Open items from the finish review
- Resolved in 5.3: the rack-size stamp's postmark drops its arc text below the large stamp and draws heavier cancel bars and needle; the default map view uses a wide cluster radius (96px, max zoom 14, start zoom 12.6) so photographed benches lead; the phone filter sheet (key and the estimated-facing note) was verified at 390x844.
- The phone sample-note card on the detail page is still unverified.
- The card flip (front to back for address and details) promised by the direction is not built; the detail page shows front and back side by side instead.
