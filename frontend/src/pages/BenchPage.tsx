import { useEffect } from "react"
import { Link, useParams } from "react-router-dom"
import { BackIcon } from "../components/Icons"
import { Stamp } from "../components/postmark/Stamp"
import { TopBar } from "../components/TopBar"
import { bestUrl, srcSet } from "../data/api"
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

  return (
    <>
      <div className="spread">
        <figure className="front" style={{ margin: 0 }}>
          <div className="photo">
            {b.hero_urls ? (
              <img
                src={bestUrl(b.hero_urls)}
                srcSet={srcSet(b.hero_urls)}
                sizes="(max-width: 900px) 100vw, 55vw"
                alt={`The bench on ${street}, looking toward ${facesText(b.faces_category)}`}
                width={960}
                height={720}
                decoding="async"
              />
            ) : null}
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
                {capital(facesText(b.faces_category).replace(/^the /, ""))}
              </dd>
              {b.material ? (
                <>
                  <dt className="caps">Material</dt>
                  <dd>{capital(b.material)}</dd>
                </>
              ) : null}
            </dl>
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

      {b.gallery.length ? (
        <section className="block" aria-labelledby="h-more">
          <div className="blockhead">
            <h2 id="h-more">More views</h2>
            <p>{b.gallery.length} other street views of this spot</p>
          </div>
          <div className="gallery">
            {b.gallery.map((g) => {
              const h = g.heading
              const look =
                h === null
                  ? "Heading not recorded"
                  : `Looking ${windName(h)} · ${h}°`
              const src = bestUrl(g.urls)
              return (
                <figure key={src}>
                  <img
                    src={src}
                    srcSet={srcSet(g.urls)}
                    alt={`Street view near the bench on ${street}, ${look.toLowerCase()}`}
                    width={g.width}
                    height={g.height}
                    loading="lazy"
                    decoding="async"
                  />
                  {h === null ? null : <MiniCompass heading={h} />}
                  <figcaption>{look}</figcaption>
                </figure>
              )
            })}
          </div>
        </section>
      ) : null}
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
