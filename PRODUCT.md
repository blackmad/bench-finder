# Product

<!-- impeccable:product-schema 1 -->

> Written 2026-11-14 without an interview: the owner asked for unattended work. Facts come from docs/RESURRECTION_PLAN.md and the owner's design brief there. Lines marked *(inferred)* still need owner confirmation.

## Platform

web

## Users

- People looking for a place to sit outdoors in a city: to read, eat lunch, watch water or a street, or catch the sun. They browse a map at home or open it on a phone nearby. *(inferred: primary audience and situation)*
- Signed-in contributors who rate benches, mark them visited or favourite, comment, and report bad or missing benches.
- The owner, who moderates reports, comments and low-confidence facings.

## Product Purpose

Bench Finder is an atlas of public benches and what you see from them. A local pipeline finds benches (OpenStreetMap, Street View, Mapillary), confirms them with detection models, works out which way each bench faces, and picks a photo of it, ideally from behind so you see the view. Success means the bench on the page is the real bench, its facing is right, and someone can pick a bench for what it looks at.

## Positioning

Every bench carries a facing direction and a view taken from behind it. No map of benches or amenities answers "what will I be looking at?". This one does, per bench.

## Operating Context

- Coverage today: about 3,229 OSM benches, mostly Amsterdam plus a little NYC. More cities come through a repeatable pipeline.
- Reads are static files: one GeoJSON for the map plus a JSON file per bench. Writes (ratings, comments, reports) go to a small Worker.
- Imagery: small hosted crops, plus Google's official Maps Embed for the interactive panorama ("view from this bench", aimed along the facing).

## Capabilities and Constraints

- Map with client-side filters: bench type, backrest, facing, and what it faces (water, street, park, square, wall, playground, other).
- Bench detail: hero image, gallery, compass and facing, Maps Embed, tags, report action.
- Accounts at launch (Firebase Auth): rating, visited/favourite, public comments, reports, and a `/me` list. Admin moderation queue.
- Must work without location permission. One responsive app, no user-agent sniffing.
- Free-tier hosting (Cloudflare). Initial JS under 200 kB gzipped; Lighthouse phone performance ≥90 and accessibility ≥95.
- Facing can be missing or low-confidence. Backless benches have an axis, not a facing. The UI must show these states honestly.

## Brand Commitments

- Name: Bench Finder. Domain: bench.blackmad.com.
- Owner-pinned: photography leads; the facing direction is the signature datum, with a compass mark on every card and marker. No emoji as UI, no glass, no gradient buttons, no debug data.

## Evidence on Hand

- Real bench locations, OSM tags and addresses in `data/benches.db`. Street-level imagery exists locally, but current hero images are unreliable until Phase 3 runs.
- No real facing data yet: only 40 OSM `direction` tags. Mockups that show facings must label them as sample data.
- No testimonials, user counts or press. Don't invent any.

## Product Principles

1. The bench is the subject: every screen shows the actual bench and what it looks at, never a generic pin.
2. Be honest about confidence: an uncertain facing looks uncertain, and a missing photo looks missing.
3. Reading is free and instant: browsing never waits on a server or a login.
4. Contribution is light: rate, mark or report in one or two taps, and moderation is quick for the owner.

## Accessibility & Inclusion

WCAG AA: contrast ≥4.5:1, real buttons, dialog focus traps, full keyboard paths. Facing must never be conveyed by colour alone.
