import { lazy, Suspense, useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import {
  BenchActions,
  BenchNotes,
  ReportRow,
} from "../components/account/BenchSocial"
import { EyeIcon, PinIcon } from "../components/Icons"
import { Photo } from "../components/Photo"
import { Stamp } from "../components/postmark/Stamp"
import { RailRow } from "../components/RailRow"
import { TopBar } from "../components/TopBar"
import { ViewFigure } from "../components/ViewFigure"
import { hasPhoto } from "../data/api"
import {
  cityName,
  headline,
  heroImage,
  lede,
  monthYear,
  seatText,
} from "../data/describe"
import { facingKind, looksAt, windName } from "../data/facing"
import { useBench, useBenches } from "../data/hooks"
import { MIN_ROW, type Row } from "../data/rows"
import type { BenchDetail, BenchFeature, GalleryImage } from "../data/types"
import "../styles/bench.css"
import NotFoundPage from "./NotFoundPage"

const MiniMap = lazy(() => import("../map/MiniMap"))

/** Tags every bench has, or that the page already shows elsewhere. */
const HIDDEN_TAGS = new Set(["amenity", "leisure", "check_date", "source"])

const capital = (s: string) => s.replace(/^\w/, (c) => c.toUpperCase())

const NEARBY_M = 1000

/** Metres between two points, close enough for "within 1 km". */
const metres = (a: [number, number], b: [number, number]) => {
  const k = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180)
  const dx = (a[0] - b[0]) * 111_320 * k
  const dy = (a[1] - b[1]) * 110_574
  return Math.hypot(dx, dy)
}

export default function BenchPage() {
  const params = useParams()
  const id = Number(params.id)
  const { data, isPending, error } = useBench(id)

  useEffect(() => {
    if (data) {
      document.title = `${headline(data)}: bench No. ${data.id}, Bench Finder`
    }
    return () => {
      document.title = "Bench Finder"
    }
  }, [data])

  if (!Number.isFinite(id)) return <NotFoundPage />

  return (
    <>
      <TopBar />
      <main className="benchpage">
        {isPending ? (
          <p className="state">Loading bench…</p>
        ) : error || !data ? (
          <p className="state" role="alert">
            Bench No. {id} could not be found.
          </p>
        ) : (
          <Spread bench={data} />
        )}
      </main>
    </>
  )
}

function Spread({ bench: b }: { bench: BenchDetail }) {
  const name = headline(b)
  const city = cityName(b)
  // Without a chosen hero, lead with the first aimed view.
  const lead = b.hero_urls
    ? null
    : (b.gallery.find((g) => g.kind === "aimed") ?? b.gallery[0] ?? null)
  const heroImg = heroImage(b)
  const shownLead = heroImg ?? lead
  const gallery = b.gallery.filter((g) => g !== shownLead)
  const tags = Object.entries(b.tags ?? {}).filter(([k]) => !HIDDEN_TAGS.has(k))
  const photographed = monthYear(shownLead?.pano_date)
  const directions = `https://www.google.com/maps/dir/?api=1&destination=${b.lat},${b.lng}&travelmode=walking`

  return (
    <>
      <section className="dhero">
        <HeroPhoto bench={b} lead={lead} name={name} />
        <div className="dtitle">
          <p className="kicker caps">
            Bench No. {b.id}
            {city ? ` · ${city}` : ""}
          </p>
          <h1>{name}</h1>
          <p className="lede">{lede(b)}</p>
          <div className="ctas">
            <a
              className="btn solid"
              href={directions}
              target="_blank"
              rel="noreferrer"
            >
              <PinIcon />
              Take me there
            </a>
            {b.embed_pano_id ? (
              <a className="btn" href="#look">
                <EyeIcon />
                Look around
              </a>
            ) : null}
            <a className="btn" href="#rate">
              Rate this bench
            </a>
          </div>
        </div>
      </section>

      <div className="sheet">
        <section className="backside" aria-label="About this bench">
          <div className="postback">
            <div className="stampslot">
              <Stamp bench={b} large />
            </div>
            <Facts bench={b} photographed={photographed} />
            <div className="rate" id="rate">
              <BenchActions benchId={b.id} />
            </div>
          </div>
          <div className="minimap">
            <Suspense fallback={null}>
              <MiniMap
                lat={b.lat}
                lng={b.lng}
                facing={b.facing}
                label={`Map around the bench at ${name}`}
              />
            </Suspense>
          </div>
        </section>

        {gallery.length ? (
          <section className="block" aria-labelledby="h-more">
            <div className="blockhead">
              <h2 id="h-more">More views</h2>
              <p>
                {gallery.length} other street{" "}
                {gallery.length === 1 ? "view" : "views"} of this spot
              </p>
            </div>
            <div className="gallery">
              {gallery.map((g) => (
                <ViewFigure
                  key={Object.values(g.urls)[0]}
                  image={g}
                  name={name}
                  sizes="(max-width: 760px) 50vw, 300px"
                />
              ))}
            </div>
          </section>
        ) : null}

        {b.embed_pano_id ? (
          <ViewFromBench
            pano={b.embed_pano_id}
            heading={b.embed_heading_deg ?? 0}
            facing={b.facing}
            street={name}
          />
        ) : null}

        <Nearby bench={b} />

        {tags.length ? (
          <section className="block" aria-labelledby="h-tags">
            <div className="blockhead">
              <h2 id="h-tags">Map data</h2>
              <p>Tags on this bench in OpenStreetMap</p>
            </div>
            <dl className="tags">
              {tags
                .sort(([a], [c]) => a.localeCompare(c))
                .map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
            </dl>
          </section>
        ) : null}

        <BenchNotes benchId={b.id} />
        <ReportRow benchId={b.id} lat={b.lat} lng={b.lng} />
      </div>
    </>
  )
}

function HeroPhoto({
  bench: b,
  lead,
  name,
}: {
  bench: BenchDetail
  lead: GalleryImage | null
  name: string
}) {
  return (
    <div className="ph">
      {b.hero_urls ? (
        <Photo
          urls={b.hero_urls}
          webp={b.hero_urls_webp}
          sizes="100vw"
          alt={`Street view of the bench at ${name}`}
          width={b.hero_width ?? 800}
          height={b.hero_height ?? 800}
          fetchPriority="high"
          decoding="async"
        />
      ) : lead ? (
        <Photo
          urls={lead.urls}
          webp={lead.urls_webp}
          sizes="100vw"
          alt={`Street view toward the bench at ${name}`}
          width={lead.width}
          height={lead.height}
          fetchPriority="high"
          decoding="async"
        />
      ) : (
        <p className="nophoto">No street-level photo of this bench yet.</p>
      )}
    </div>
  )
}

function facingSource(b: BenchDetail): string {
  if (facingKind(b) === "estimated") {
    return `estimated from street views, ${Math.round((b.facing_confidence ?? 0) * 100)}%`
  }
  return b.facing_method === "human"
    ? "confirmed by a visitor"
    : "mapped in OpenStreetMap"
}

function Facts({
  bench: b,
  photographed,
}: {
  bench: BenchDetail
  photographed: string | null
}) {
  const kind = facingKind(b)
  const seat = seatText(b.backrest)
  const looks = looksAt(b.faces_category)
  return (
    <dl>
      {looks || b.faces_text ? (
        <>
          <dt className="caps">Looks at</dt>
          <dd>
            {looks ?? capital(b.faces_text as string)}
            {looks && b.faces_text ? <small> {b.faces_text}</small> : null}
          </dd>
        </>
      ) : null}
      <dt className="caps">{looks ? "Compass" : "Facing"}</dt>
      <dd>
        {kind && b.facing !== null ? (
          <>
            <span className="num">
              {kind === "estimated" ? "≈ " : ""}
              {windName(b.facing)} · {Math.round(b.facing)}°
            </span>{" "}
            <small>{facingSource(b)}</small>
          </>
        ) : (
          <>
            Not known yet <small>no direction in the map data</small>
          </>
        )}
      </dd>
      <dt className="caps">Seat</dt>
      <dd>{seat ?? "Not recorded"}</dd>
      {b.material ? (
        <>
          <dt className="caps">Material</dt>
          <dd>{capital(b.material)}</dd>
        </>
      ) : null}
      {photographed ? (
        <>
          <dt className="caps">Photo</dt>
          <dd>{photographed}</dd>
        </>
      ) : null}
      <dt className="caps">Where</dt>
      <dd>
        <span className="num">
          {b.lat.toFixed(5)}° N, {b.lng.toFixed(5)}° E
        </span>{" "}
        <small>
          <a
            href={`https://www.openstreetmap.org/?mlat=${b.lat}&mlon=${b.lng}#map=19/${b.lat}/${b.lng}`}
            rel="noreferrer"
          >
            OpenStreetMap
          </a>
        </small>
      </dd>
    </dl>
  )
}

/** Photographed benches within a kilometre, nearest first. */
function Nearby({ bench }: { bench: BenchDetail }) {
  const { data } = useBenches()
  const row = useMemo<Row | null>(() => {
    if (!data) return null
    const here: [number, number] = [bench.lng, bench.lat]
    const near = data
      .filter((f) => f.properties.id !== bench.id && hasPhoto(f))
      .map((f) => [f, metres(here, f.geometry.coordinates)] as const)
      .filter(([, m]) => m <= NEARBY_M)
      .sort((a, b) => a[1] - b[1])
      .map(([f]) => f as BenchFeature)
    return near.length >= MIN_ROW
      ? { key: "nearby", title: "Nearby benches", note: "", benches: near }
      : null
  }, [data, bench.id, bench.lat, bench.lng])
  if (!row) return null
  return (
    <div className="block nearby">
      <RailRow
        row={row}
        selectedId={null}
        countLabel={`${row.benches.length} within 1 km`}
      />
    </div>
  )
}

const EMBED_KEY = import.meta.env.VITE_GOOGLE_MAPS_EMBED_KEY as
  | string
  | undefined

/**
 * Street View from the best nearby panorama, opened looking at the bench.
 * The iframe only loads on request, so the page stays light; without an Embed API
 * key it links out to Google Maps instead.
 */
function ViewFromBench({
  pano,
  heading,
  facing,
  street,
}: {
  pano: string
  /** Bearing from the panorama toward the bench. */
  heading: number
  facing: number | null
  street: string
}) {
  const [open, setOpen] = useState(false)
  const h = Math.round(heading)
  const outUrl = `https://www.google.com/maps/@?api=1&map_action=pano&pano=${encodeURIComponent(pano)}&heading=${h}&pitch=0&fov=80`
  return (
    <section className="block" aria-labelledby="h-view" id="look">
      <div className="blockhead">
        <h2 id="h-view">This spot in Street View</h2>
        <p>
          Opens looking {windName(h)} at the bench
          {facing === null
            ? ""
            : `; turn ${windName(facing)} to see what it faces`}
        </p>
      </div>
      {!EMBED_KEY ? (
        <p className="embedlink">
          <a href={outUrl} target="_blank" rel="noreferrer">
            Open this view in Google Maps
          </a>
        </p>
      ) : open ? (
        <iframe
          className="embed"
          title={`Street View from the bench on ${street}`}
          src={`https://www.google.com/maps/embed/v1/streetview?key=${EMBED_KEY}&pano=${encodeURIComponent(pano)}&heading=${h}&pitch=0&fov=80`}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          allowFullScreen
        />
      ) : (
        <div className="embed placeholder">
          <button type="button" className="btn" onClick={() => setOpen(true)}>
            Look around from here
          </button>
        </div>
      )}
    </section>
  )
}
