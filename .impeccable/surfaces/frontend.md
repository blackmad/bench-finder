---
version: 1
slug: "frontend"
primary_target: "frontend"
related_targets: []
---

Scope: whole frontend app (map/list `/`, bench detail `/bench/:id`, `/me`, admin). Visitor mode: Experience on browse and detail; Operate on filters, account and moderation.
Audience and job: people choosing an outdoor seat by what it looks at. They browse on a desktop at home or on a phone outside in daylight.
Constraint: owner-pinned. No emoji UI, no glass, no gradient buttons, no debug data. A compass mark on every card and marker.

## Direction contract
THESIS: Every bench is a picture postcard of its own view, postmarked with the direction it faces. This replaces the category default of grey pins plus rounded cards.
OWN-WORLD: White card stock (#F6F6F1), ink (#141414), airmail blue (#1E4FA3), and vermilion (#E23B1E) reserved for the selected bench. Photos sit inside a white printed border. Postmark rings with cancel bars carry the facing; known facings use solid ink, inferred ones a hairline. Archivo, with expanded caps for captions and serials.
STORY: The visitor sees benches as views. They pick one by what it faces, open its card, flip to the back for address and details, then open "view from this bench".
FIRST VIEWPORT: Desktop has the map (≈58%) with postmark markers, and a rack of postcards on the right with filters above it. On a phone, the map has a swipeable postcard stack docked at the bottom.
FORM: Picture postcard rack (#4 of 7), seed fc8012af.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
