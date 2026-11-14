import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import {
  BenchActions,
  BenchNotes,
  ReportRow,
} from "../components/account/BenchSocial"
import { BackIcon } from "../components/Icons"
import { Photo } from "../components/Photo"
import { Stamp } from "../components/postmark/Stamp"
import { TopBar } from "../components/TopBar"
import { facesText, isKnown, WIND_LONG, windName } from "../data/facing"
import { useBench } from "../data/hooks"
import type { BenchDetail } from "../data/types"
import "../styles/bench.css"
import NotFoundPage from "./NotFoundPage"

const HEADLINE: Record<string, string> = {
  water: "Looks out over the water",
  park: "Looks into the park",
  square: "Looks across the square",
  street: "Watches the street",
}

/** Tags every bench has, or that the page already shows elsewhere. */
const HIDDEN_TAGS = new Set(["amenity", "leisure", "check_date", "source"])

const capital = (s: string) => s.replace(/^\w/, (c) => c.toUpperCase())

export default function BenchPage() {
  const params = useParams()
  const id = Number(params.id)
  const { data, isPending, error } = useBench(id)

  useEffect(() => {
    if (data) {
      document.title = `${data.address ?? "Unnamed path"}: bench No. ${data.id}, Bench Finder`
    }
    return () => {
      document.title = "Bench Finder"
    }
  }, [data])

  if (!Number.isFinite(id)) return <NotFoundPage />

  return (
    <>
      <TopBar />
      <main className="page">
        <Link className="crumb" to="/">
          <BackIcon />
          Back to the map
        </Link>
        {isPending ? (
          <p className="state">Loading bench...</p>
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
  const street = b.address_full.street ?? b.address ?? "Unnamed path"
  const known = isKnown(b)
  const w = b.facing === null ? null : windName(b.facing)
  const seat =
    b.bench_type === "backrest"
      ? "backrest bench"
      : b.bench_type === "backless"
        ? "backless bench"
        : "bench"
  const roadName = street.replace(/\s\d.*$/, "")
  const conf = Math.round((b.facing_confidence ?? 0) * 100)
  // Until views are classified there is no chosen hero; lead with the first aimed view.
  const lead = b.hero_urls
    ? null
    : (b.gallery.find((g) => g.kind === "aimed") ?? b.gallery[0] ?? null)
  const gallery = lead ? b.gallery.filter((g) => g !== lead) : b.gallery
  const tags = Object.entries(b.tags ?? {}).filter(([k]) => !HIDDEN_TAGS.has(k))

  return (
    <>
      <div className="spread">
        <figure className="front" style={{ margin: 0 }}>
          <div className="photo">
            {b.hero_urls ? (
              <Photo
                urls={b.hero_urls}
                webp={b.hero_urls_webp}
                sizes="(max-width: 900px) calc(100vw - 64px), 640px"
                alt={`The bench on ${street}, seen from behind, looking toward ${facesText(b.faces_category)}`}
                width={b.hero_width ?? 960}
                height={b.hero_height ?? 720}
                fetchPriority="high"
                decoding="async"
              />
            ) : lead ? (
              <Photo
                urls={lead.urls}
                webp={lead.urls_webp}
                sizes="(max-width: 900px) calc(100vw - 64px), 640px"
                alt={`Street view toward the bench on ${street}`}
                width={lead.width}
                height={lead.height}
                fetchPriority="high"
                decoding="async"
              />
            ) : (
              <p className="nophoto">
                No street-level photo of this bench yet.
              </p>
            )}
          </div>
          <div className="stampslot">
            <Stamp bench={b} large />
          </div>
          <figcaption className="caption">
            <span className="caps">{street}</span>
            <span className="serial">No.&nbsp;{b.id}</span>
          </figcaption>
        </figure>

        <article className="back" aria-label="About this bench">
          <div className="message">
            <h1>{HEADLINE[b.faces_category ?? ""] ?? "A bench"}</h1>
            <p className="lede">
              A {seat} on {roadName},{" "}
              {w
                ? `${known ? "facing" : "probably facing"} ${WIND_LONG[w]}`
                : "facing a direction not yet known"}
              {b.material ? `, made of ${b.material}` : ""}.
            </p>
            <dl>
              <dt className="caps">Facing</dt>
              <dd>
                {w && b.facing !== null ? (
                  <>
                    <span className="num">
                      {w} · {b.facing}°
                    </span>
                    <small>
                      {known ? (
                        "From the OpenStreetMap direction tag"
                      ) : (
                        <span className="conf">
                          Estimated from street views
                          <span className="meter" aria-hidden="true">
                            <b style={{ width: `${conf}%` }} />
                          </span>
                          {conf}%
                        </span>
                      )}
                    </small>
                  </>
                ) : (
                  "Not known yet"
                )}
              </dd>
              <dt className="caps">Seat</dt>
              <dd>
                {b.bench_type === "backrest"
                  ? "Backrest"
                  : b.bench_type === "backless"
                    ? "No backrest"
                    : "Not recorded"}
              </dd>
              <dt className="caps">Looks at</dt>
              <dd>
                {b.faces_category
                  ? capital(facesText(b.faces_category).replace(/^the /, ""))
                  : "Not known yet"}
              </dd>
              {b.material ? (
                <>
                  <dt className="caps">Material</dt>
                  <dd>{capital(b.material)}</dd>
                </>
              ) : null}
            </dl>
            <BenchActions benchId={b.id} />
          </div>
          <div className="address">
            <div className="stampslot">
              <Stamp bench={b} decorative />
            </div>
            <div className="lines">
              <div className="caps">Bench No. {b.id}</div>
              <div>
                {street}
                {b.address_full.number ? ` ${b.address_full.number}` : ""}
              </div>
              <div>
                {b.address_full.postcode ? `${b.address_full.postcode} ` : ""}
                {b.address_full.city ?? ""}
              </div>
              <div>{b.address_full.country ?? ""}</div>
            </div>
            <p className="coords num">
              {b.lat.toFixed(5)}° N, {b.lng.toFixed(5)}° E ·{" "}
              <a
                href={`https://www.openstreetmap.org/?mlat=${b.lat}&mlon=${b.lng}#map=19/${b.lat}/${b.lng}`}
                rel="noreferrer"
              >
                Open in OpenStreetMap
              </a>
            </p>
          </div>
        </article>
      </div>

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
            {gallery.map((g) => {
              const h = g.heading
              const look =
                h === null
                  ? "Heading not recorded"
                  : `Looking ${windName(h)} · ${h}°`
              const key = Object.values(g.urls)[0]
              return (
                <figure key={key}>
                  <Photo
                    urls={g.urls}
                    webp={g.urls_webp}
                    sizes="(max-width: 760px) 50vw, 300px"
                    alt={`Street view near the bench on ${street}, ${look.toLowerCase()}`}
                    width={g.width}
                    height={g.height}
                    loading="lazy"
                    decoding="async"
                  />
                  {h === null ? null : <MiniCompass heading={h} />}
                  <figcaption>
                    {look}
                    {g.pano_date ? (
                      <span className="when"> · {photoDate(g.pano_date)}</span>
                    ) : null}
                  </figcaption>
                </figure>
              )
            })}
          </div>
        </section>
      ) : null}

      {b.embed_pano_id ? (
        <ViewFromBench
          pano={b.embed_pano_id}
          heading={b.embed_heading_deg ?? 0}
          facing={b.facing}
          street={street}
        />
      ) : null}

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
    </>
  )
}

function MiniCompass({ heading }: { heading: number }) {
  return (
    <svg className="minicompass" viewBox="-12 -12 24 24" aria-hidden="true">
      <circle
        r="10.5"
        fill="var(--color-stamp-paper)"
        stroke="var(--color-ink)"
        strokeWidth="1"
      />
      <g transform={`rotate(${heading})`}>
        <line y1="3" y2="-6" stroke="var(--color-ink)" strokeWidth="1.6" />
        <path d="M0 -9 l-2.6 4 h5.2z" fill="var(--color-ink)" />
      </g>
    </svg>
  )
}

const photoDate = (ym: string) => {
  const [y, m] = ym.split("-").map(Number)
  if (!y) return ym
  return m
    ? new Date(y, m - 1).toLocaleDateString(undefined, {
        month: "short",
        year: "numeric",
      })
    : String(y)
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
    <section className="block" aria-labelledby="h-view">
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
