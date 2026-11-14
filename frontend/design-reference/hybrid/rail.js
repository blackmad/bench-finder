// Shared bits for the Picture Rail mock: the round compass seal, tiles, words.
import { windName } from "../postmark.js";
export { windName };

export const B = window.MOCK_BENCHES.map((b) => ({ ...b, src: b.known ? "osm" : "sample" }));
export const byId = new Map(B.map((b) => [b.id, b]));
const LONG = { N: "north", NNE: "north-north-east", NE: "north-east", ENE: "east-north-east", E: "east", ESE: "east-south-east", SE: "south-east", SSE: "south-south-east", S: "south", SSW: "south-south-west", SW: "south-west", WSW: "west-south-west", W: "west", WNW: "west-north-west", NW: "north-west", NNW: "north-north-west" };
export const windLong = (d) => LONG[windName(d)];
export const HEAD = { water: "Looks out over the water", park: "Looks into the park", street: "Watches the street" };
export const LOOKS = { water: "the water", park: "the park", street: "the street" };
export const facingLine = (b) => (b.known ? `${windName(b.facing)} ${b.facing}°` : `≈ ${windName(b.facing)} ${b.facing}°`);

/** A round postmark-compass that sits on a photo. Solid ink = mapped facing; dashed airmail = estimated. */
export function seal(b, { size = 40, selected = false } = {}) {
  const col = selected ? "#e23b1e" : b.known ? "#141414" : "#1e4fa3";
  const R = 15;
  const ticks = Array.from({ length: 8 }, (_, i) => {
    const a = (i * 45 * Math.PI) / 180, l = i % 2 ? 1.8 : 3;
    return `<line x1="${Math.sin(a) * R}" y1="${-Math.cos(a) * R}" x2="${Math.sin(a) * (R - l)}" y2="${-Math.cos(a) * (R - l)}"/>`;
  }).join("");
  const needle = b.known
    ? `<line y1="5" y2="-8" stroke-width="2"/><path d="M0 -12.5 l-3.6 5.6 h7.2z" fill="${col}" stroke="none"/>`
    : `<line y1="5" y2="-7.5" stroke-width="1.3" stroke-dasharray="2 1.6"/><path d="M0 -12.5 l-3.4 5.4 h6.8z" fill="#fbfbf7" stroke-width="1.2"/>`;
  const label = b.known ? `Faces ${windLong(b.facing)} (${b.facing}°), mapped` : `Probably faces ${windLong(b.facing)} (${b.facing}°), estimated ${Math.round(b.conf * 100)}%`;
  return `<svg viewBox="-19 -19 38 38" width="${size}" height="${size}" role="img" aria-label="${label}"><title>${label}</title>
    <circle r="18" fill="#fbfbf7"/><circle r="${R}" fill="none" stroke="#141414" stroke-width=".8"/>
    <g stroke="#141414" stroke-width=".8">${ticks}</g>
    <text y="-8.6" text-anchor="middle" font-size="4.6" font-weight="800" font-family="Archivo" fill="#141414">N</text>
    <g transform="rotate(${b.facing})" stroke="${col}" fill="none" stroke-linecap="round">${needle}<circle r="1.9" fill="${col}" stroke="none"/></g>
  </svg>`;
}

export function tile(b, { selected = false } = {}) {
  return `<a class="tile" href="bench.html?id=${b.id}" data-id="${b.id}"${selected ? " aria-current" : ""}>
    <div class="ph"><img src="${b.img}" alt="The view from the bench on ${b.addr}, looking toward ${LOOKS[b.cat]}" loading="lazy" width="900" height="675"/><span class="seal">${seal(b, { size: 38, selected })}</span></div>
    <div class="cap"><span class="caps">${b.addr}</span><small>${b.known ? "" : '<span class="est">≈</span> '}Faces ${windName(b.facing)} · ${b.facing}° · ${b.known ? "mapped" : "estimated"}</small></div>
  </a>`;
}

export const ICON = {
  search: '<svg class="icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/></svg>',
  user: '<svg class="icon" viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20c1.3-3.6 4.2-5.4 7.5-5.4s6.2 1.8 7.5 5.4"/></svg>',
  near: '<svg class="icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22"/></svg>',
  pin: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/></svg>',
  eye: '<svg class="icon" viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/></svg>',
  star: '<svg viewBox="0 0 24 24"><path d="m12 3.8 2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.8l-5.1 2.7 1-5.7-4.1-4 5.7-.8z"/></svg>',
};

export function header() {
  return `<header class="bar">
    <a class="wordmark caps" href="index.html">Bench Finder</a>
    <span class="search">${ICON.search}<span>Search<span class="ph-long"> a place</span></span></span>
    <span class="spacer"></span>
    <button class="textbtn" type="button">${ICON.user}<span class="signin-label">Sign in</span></button>
  </header>`;
}

/** Basemap re-inked as card stock with airmail water (the Rack's map). */
export function inkMap(map) {
  for (const l of map.getStyle().layers) {
    if (l.type === "background") map.setPaintProperty(l.id, "background-color", "#f6f6f1");
    if (/water/.test(l.id) && l.type === "fill") map.setPaintProperty(l.id, "fill-color", "#cfdbee");
    if (/park|landuse|landcover|wood|grass/.test(l.id) && l.type === "fill") map.setPaintProperty(l.id, "fill-color", "#e6eadc");
    if (l.type === "symbol" && l.layout?.["text-field"]) map.setPaintProperty(l.id, "text-color", "#6b6b66");
  }
}
