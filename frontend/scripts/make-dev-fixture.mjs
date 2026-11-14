// Generates frontend/public/data/ (manifest, GeoJSON, per-bench JSON) from the
// design-reference sample data, and copies the Street View crops it references.
// Usage: node scripts/make-dev-fixture.mjs [path/to/design-reference/img]
// The images are gitignored; only the JSON is committed.
import { createHash } from "node:crypto"
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import vm from "node:vm"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const ref = join(root, "design-reference")
const FALLBACK_IMG =
  "/Users/blackmad/bench_finder/frontend/design-reference/img"
const imgSrc = [
  process.argv.slice(2).find((a) => !a.startsWith("--")),
  join(ref, "img"),
  FALLBACK_IMG,
]
  .filter(Boolean)
  .find((p) => existsSync(p))
const out = join(root, "public", "data")
if (
  process.argv.includes("--if-missing") &&
  existsSync(join(out, "manifest.json"))
) {
  process.exit(0)
}

const sandbox = { window: {} }
vm.runInNewContext(readFileSync(join(ref, "data.js"), "utf8"), sandbox)
const benches = sandbox.window.BENCHES
const gallery = sandbox.window.GALLERY ?? {}

const IMG_W = 960
const imgUrl = (p) => (p ? p.replace(/^img\//, "img/") : null)

function props(b) {
  const known = b.src === "osm"
  return {
    id: b.id,
    lat: b.lat,
    lng: b.lng,
    facing: b.facing,
    facing_confidence: known ? 1 : b.conf,
    facing_method: known ? "osm_tag" : "vlm",
    axis_only: false,
    bench_type: b.type === "backrest" || b.type === "backless" ? b.type : null,
    backrest:
      b.type === "backrest" ? true : b.type === "backless" ? false : null,
    faces_category: b.faces ?? null,
    hero_key: b.img ? `hero/${b.id}` : null,
    hero_urls: b.img ? { [IMG_W]: imgUrl(b.img) } : null,
    address: b.street ?? null,
  }
}

const features = benches.map((b) => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: [b.lng, b.lat] },
  properties: props(b),
}))
const geojson = JSON.stringify({ type: "FeatureCollection", features })
const hash = createHash("sha1").update(geojson).digest("hex").slice(0, 10)
const geojsonName = `benches.${hash}.geojson`

rmSync(out, { recursive: true, force: true })
mkdirSync(join(out, "bench"), { recursive: true })
writeFileSync(join(out, geojsonName), geojson)

for (const b of benches) {
  const g = gallery[b.id] ?? []
  const detail = {
    ...props(b),
    material: b.material ?? null,
    address_full: {
      street: b.street ?? null,
      number: b.num ?? null,
      postcode: b.pc ?? null,
      city: "Amsterdam",
      country: "Netherlands",
    },
    gallery: g.map((x) => ({
      urls: { 640: imgUrl(x.src) },
      width: 640,
      height: 640,
      heading: x.heading ?? null,
    })),
    embed_pano_id: null,
    embed_heading_deg: b.facing,
  }
  writeFileSync(join(out, "bench", `${b.id}.json`), JSON.stringify(detail))
}

writeFileSync(
  join(out, "manifest.json"),
  JSON.stringify({
    version: 1,
    generated_at: new Date().toISOString(),
    count: benches.length,
    benches: geojsonName,
    bench_dir: "bench/",
  })
)

if (imgSrc) {
  mkdirSync(join(out, "img"), { recursive: true })
  for (const f of readdirSync(imgSrc)) {
    copyFileSync(join(imgSrc, f), join(out, "img", f))
  }
  console.log(`copied images from ${imgSrc}`)
} else {
  console.warn("no image directory found; photos will be missing")
}
console.log(`wrote ${benches.length} benches, ${geojsonName}`)
