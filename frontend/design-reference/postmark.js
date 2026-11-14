// Bench Finder design reference: the stamp/postmark compass and map marker art.
const WINDS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
export const windName = (deg) => WINDS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];
const FACES = { water: "the water", park: "the park", street: "the street", square: "the square", wall: "a wall", playground: "a playground" };
export const facesText = (f) => FACES[f] || "something";
export const isKnown = (b) => b.src === "osm";

/**
 * A perforated postage stamp whose printed face is a compass, cancelled by a postmark ring.
 * known=true: solid arrow (OSM tag or high-confidence). known=false: hairline dashed arrow + confidence.
 */
export function stampSVG(b, { selected = false, large = false } = {}) {
  const W = 74, H = 88, r = 2.4, step = 7.4;
  const holes = [];
  for (let x = step / 2; x < W; x += step) holes.push(`<circle cx="${x.toFixed(1)}" cy="0" r="${r}"/><circle cx="${x.toFixed(1)}" cy="${H}" r="${r}"/>`);
  for (let y = step / 2; y < H; y += step) holes.push(`<circle cx="0" cy="${y.toFixed(1)}" r="${r}"/><circle cx="${W}" cy="${y.toFixed(1)}" r="${r}"/>`);
  const id = `p${b.id}${large ? "l" : ""}${Math.random().toString(36).slice(2, 6)}`;
  const known = isKnown(b);
  const accent = selected ? "var(--vermilion)" : known ? "var(--ink)" : "var(--airmail)";
  const cx = 37, cy = 37, R = 21;
  const ticks = Array.from({ length: 16 }, (_, i) => {
    const a = (i * 22.5 * Math.PI) / 180, l = i % 4 === 0 ? 4 : 2;
    return `<line x1="${cx + Math.sin(a) * R}" y1="${cy - Math.cos(a) * R}" x2="${cx + Math.sin(a) * (R - l)}" y2="${cy - Math.cos(a) * (R - l)}"/>`;
  }).join("");
  const arrow = known
    ? `<g transform="rotate(${b.facing} ${cx} ${cy})" stroke="${accent}" fill="${accent}"><line x1="${cx}" y1="${cy + 9}" x2="${cx}" y2="${cy - 12}" stroke-width="2.2"/><path d="M${cx} ${cy - 18} l-5 8 h10z" stroke="none"/><circle cx="${cx}" cy="${cy}" r="2.4" stroke="none"/></g>`
    : `<g transform="rotate(${b.facing} ${cx} ${cy})" stroke="${accent}" fill="none"><line x1="${cx}" y1="${cy + 9}" x2="${cx}" y2="${cy - 11}" stroke-width="1.1" stroke-dasharray="2.4 2"/><path d="M${cx} ${cy - 18} l-4.5 7.5 h9z" stroke-width="1.1"/><circle cx="${cx}" cy="${cy}" r="2" stroke-width="1.1"/></g>`;
  const label = known ? `${windName(b.facing)} ${b.facing}°` : `≈ ${windName(b.facing)}`;
  const title = known
    ? `Faces ${windName(b.facing)} (${b.facing}°), from the OpenStreetMap direction tag`
    : `Probably faces ${windName(b.facing)} (${b.facing}°), estimated with ${Math.round(b.conf * 100)}% confidence`;
  return `<svg class="stamp${large ? " lg" : ""}${selected ? " stamping" : ""}" viewBox="0 0 ${W} ${H}" overflow="visible" role="img" aria-label="${title}">
  <title>${title}</title>
  <defs><mask id="${id}"><rect width="${W}" height="${H}" fill="#fff"/><g fill="#000">${holes.join("")}</g></mask></defs>
  <rect width="${W}" height="${H}" fill="#fbfbf7" mask="url(#${id})"/>
  <rect x="5.5" y="5.5" width="${W - 11}" height="${H - 11}" fill="none" stroke="var(--ink)" stroke-width=".7"/>
  <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="var(--ink)" stroke-width=".8"/>
  <g stroke="var(--ink)" stroke-width=".8">${ticks}</g>
  <text x="${cx}" y="${cy - R - 3.2}" text-anchor="middle" font-size="6.2" font-weight="800" font-family="Archivo" style="font-variation-settings:'wdth' 125" fill="var(--ink)">N</text>
  ${arrow}
  <text x="${cx}" y="76" text-anchor="middle" font-size="8.6" font-weight="700" font-family="Archivo" style="font-variation-settings:'wdth' 118;font-variant-numeric:tabular-nums" fill="${known || selected ? accent : "var(--ink)"}">${label}</text>
  ${postmark(b, selected, id)}
</svg>`;
}

function postmark(b, selected, id) {
  // The cancellation carries the facing: arc text names it, cancel bars run along the heading.
  const known = isKnown(b);
  const ink = selected ? "var(--vermilion)" : "var(--ink)";
  const x = 4, y = 78, r = 15;
  const sw = known ? 0.95 : 0.6, dash = known ? "" : 'stroke-dasharray="1.6 1.4"';
  const bars = [-4.5, 0, 4.5].map((o) => `<path d="M${x + o} ${y - r - 2} q -2 -3.5 0 -7 t 0 -7 t 0 -7" />`).join("");
  const arcText = `${known ? "" : "≈ "}${windName(b.facing)} · ${b.facing}°`;
  return `<g opacity=".78" stroke="${ink}" fill="none" stroke-width="${sw}" ${dash}>
    <g transform="rotate(${b.facing} ${x} ${y})">${bars}</g>
    <circle cx="${x}" cy="${y}" r="${r}" fill="rgb(251 251 247 / .55)"/><circle cx="${x}" cy="${y}" r="${r - 4.6}"/>
    <path id="${id}t" d="M${x - r + 2.3} ${y} a ${r - 2.3} ${r - 2.3} 0 0 1 ${2 * (r - 2.3)} 0" stroke="none"/>
    <text font-size="3.7" font-weight="700" font-family="Archivo" style="font-variation-settings:'wdth' 118;letter-spacing:.2px" fill="${ink}" stroke="none"><textPath href="#${id}t" startOffset="50%" text-anchor="middle">${arcText}</textPath></text>
    <g transform="rotate(${b.facing} ${x} ${y})" stroke-dasharray="none"><line x1="${x}" y1="${y + 4}" x2="${x}" y2="${y - 6}" stroke-width="${known ? 1.3 : 0.8}"/><path d="M${x} ${y - 8.5} l-2.2 3.4 h4.4z" fill="${known ? ink : "none"}"/></g>
  </g>`;
}

/** Map marker art: a small ring with a facing needle, drawn pointing north (MapLibre rotates it). */
export function markerImage(kind) {
  const S = 44, c = S / 2, dpr = 2;
  const cv = document.createElement("canvas");
  cv.width = S * dpr; cv.height = S * dpr;
  const g = cv.getContext("2d");
  g.scale(dpr, dpr);
  const col = kind === "sel" ? "#e23b1e" : kind === "est" ? "#1e4fa3" : "#141414";
  g.strokeStyle = col; g.fillStyle = col; g.lineCap = "round";
  g.lineWidth = kind === "est" ? 1.4 : 2.2;
  if (kind === "est") g.setLineDash([2.5, 2.2]);
  g.beginPath(); g.moveTo(c, c - 6); g.lineTo(c, c - 17); g.stroke();
  g.setLineDash([]);
  g.beginPath(); g.moveTo(c, c - 21); g.lineTo(c - 3.6, c - 14.5); g.lineTo(c + 3.6, c - 14.5); g.closePath();
  if (kind === "est") { g.lineWidth = 1.2; g.stroke(); } else g.fill();
  g.beginPath(); g.arc(c, c, kind === "sel" ? 6.5 : 5, 0, Math.PI * 2);
  g.fillStyle = kind === "sel" ? "#e23b1e" : "#fbfbf7"; g.fill();
  g.lineWidth = kind === "sel" ? 0 : kind === "est" ? 1.4 : 2; g.strokeStyle = col; if (kind !== "sel") g.stroke();
  return { width: S * dpr, height: S * dpr, data: new Uint8Array(g.getImageData(0, 0, S * dpr, S * dpr).data.buffer) };
}

export const ICONS = {
  search: '<svg class="icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/></svg>',
  user: '<svg class="icon" viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20c1.3-3.6 4.2-5.4 7.5-5.4s6.2 1.8 7.5 5.4"/></svg>',
  check: '<svg viewBox="0 0 12 12" fill="none" stroke-linecap="round"><path d="M2 6.5 4.8 9 10 3"/></svg>',
  sliders: '<svg class="icon" viewBox="0 0 24 24"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>',
  back: '<svg class="icon" viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  flag: '<svg class="icon" viewBox="0 0 24 24"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>',
  turn: '<svg class="icon" viewBox="0 0 24 24"><path d="M4 12a8 8 0 0 1 13.7-5.6L20 9M20 4v5h-5"/><path d="M20 12a8 8 0 0 1-13.7 5.6L4 15M4 20v-5h5"/></svg>',
  eye: '<svg class="icon" viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/></svg>',
  star: '<svg class="icon" viewBox="0 0 24 24"><path d="m12 3.8 2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.8l-5.1 2.7 1-5.7-4.1-4 5.7-.8z"/></svg>',
  pin: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/></svg>',
};
