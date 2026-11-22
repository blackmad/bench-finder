import { useEffect, useId, useRef, useState } from "react"
import { focusStyle } from "../data/api"
import { headline, heroImage, lede, monthYear } from "../data/describe"
import { useBench } from "../data/hooks"
import type { BenchDetail, BenchProps } from "../data/types"
import { useSwipe } from "../lib/useSwipe"
import { Away } from "./Away"
import { BenchActions, BenchNotes, ReportRow } from "./account/BenchSocial"
import { Facts, ViewFromBench } from "./BenchDetails"
import { PinIcon } from "./Icons"
import { Lightbox } from "./Lightbox"
import { Photo } from "./Photo"
import { ViewFigure } from "./ViewFigure"

interface Props {
  /** The bench's map properties, when the GeoJSON has it (renders at once). */
  bench: BenchProps | null
  id: number
  onClose: () => void
  /** Swipe left/right (phones): the next or previous bench nearby. */
  onStep?: (dir: 1 | -1) => void
}

/**
 * A bench opened in the rail: its photo large, the title card, its facts and
 * rating, the other views, Street View, notes and the report link. The map stays beside
 * it with the bench marked in vermilion; the URL carries `?bench=ID`.
 */
export function BenchPreview({ bench, id, onClose, onStep }: Props) {
  const swipe = useSwipe(onStep)
  const { data: detail, isPending } = useBench(id)
  const b: BenchProps | null = detail ?? bench
  const titleId = useId()
  const ref = useRef<HTMLElement>(null)
  const [viewing, setViewing] = useState<number | null>(null)

  // Bring the preview into view and give keyboard users its heading. The
  // parent keys this component by bench id, so this runs once per bench.
  useEffect(() => {
    ref.current?.scrollIntoView({ block: "nearest" })
    ref.current
      ?.querySelector<HTMLElement>("h2")
      ?.focus({ preventScroll: true })
  }, [])

  const back = (
    <div className="pvbar">
      <button type="button" className="linkbtn" onClick={onClose}>
        <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M15 5l-7 7 7 7" />
        </svg>
        Benches in view
      </button>
    </div>
  )

  useTabTitle(b)

  if (!b) {
    return (
      <section className="pv" ref={ref} aria-labelledby={titleId} {...swipe}>
        {back}
        <h2 id={titleId} className="railnote" tabIndex={-1}>
          {isPending ? "Loading bench…" : `Bench No. ${id} could not be found.`}
        </h2>
      </section>
    )
  }

  const name = headline(b)
  const hero = detail ? heroImage(detail) : null
  const views = detail?.gallery.filter((g) => g !== hero) ?? []
  const directions = `https://www.google.com/maps/dir/?api=1&destination=${b.lat},${b.lng}&travelmode=walking`

  return (
    <section className="pv" ref={ref} aria-labelledby={titleId}>
      {back}
      <div className="ph">
        {b.hero_urls ? (
          <Photo
            urls={b.hero_urls}
            webp={b.hero_urls_webp}
            sizes="(max-width: 760px) 100vw, 58vw"
            alt={`Street view of the bench at ${name}`}
            width={b.hero_width ?? 800}
            height={b.hero_height ?? 800}
            style={focusStyle(b.hero_focus)}
            decoding="async"
          />
        ) : (
          <p className="nophoto">No street-level photo of this bench yet.</p>
        )}
        <Away lat={b.lat} lng={b.lng} />
      </div>
      <div className="titlecard">
        <h2 id={titleId} tabIndex={-1}>
          {name}
        </h2>
        <p className="lede">{detail ? lede(detail) : " "}</p>
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
        </div>
      </div>
      <FactsCard bench={detail} id={b.id} />
      {views.length ? (
        <div className="pvviews">
          <div className="rowhead">
            <h3 className="caps">More views</h3>
            <small className="num">
              {views.length} other street{" "}
              {views.length === 1 ? "view" : "views"}
            </small>
          </div>
          <div className="strip">
            {views.map((g, i) => (
              <ViewFigure
                key={Object.values(g.urls)[0]}
                image={g}
                name={name}
                sizes="(max-width: 760px) 60vw, 220px"
                onOpen={() => setViewing(i)}
              />
            ))}
          </div>
          {viewing !== null ? (
            <Lightbox
              images={views}
              index={viewing}
              name={name}
              onIndex={setViewing}
              onClose={() => setViewing(null)}
            />
          ) : null}
        </div>
      ) : null}
      <StreetView bench={detail} name={name} />
      <BenchNotes benchId={b.id} />
      <div className="pvreport">
        <ReportRow benchId={b.id} />
      </div>
    </section>
  )
}

/** What it looks at, which way it faces, the seat, the photo date; the rating. */
function FactsCard({ bench: d, id }: { bench?: BenchDetail; id: number }) {
  return (
    <div className="pvfacts">
      {d ? (
        <Facts
          bench={d}
          photographed={monthYear((heroImage(d) ?? d.gallery[0])?.pano_date)}
        />
      ) : null}
      <BenchActions benchId={id} />
    </div>
  )
}

function StreetView({ bench: d, name }: { bench?: BenchDetail; name: string }) {
  if (!d) return null
  const at: [number, number] | null =
    d.embed_lat != null && d.embed_lng != null
      ? [d.embed_lat, d.embed_lng]
      : null
  // Data published before embed_lat existed can still carry an Apple or city
  // panorama id; only a Google-shaped id may reach Google's embed.
  const pano =
    d.embed_pano_id && /^[A-Za-z0-9_-]{22}$/.test(d.embed_pano_id)
      ? d.embed_pano_id
      : null
  if (!pano && !at) return null
  return (
    <ViewFromBench
      pano={pano}
      at={at}
      heading={d.embed_heading_deg ?? 0}
      facing={d.facing}
      street={name}
    />
  )
}

/** The tab (and a shared link's title) names the open bench. */
function useTabTitle(b: BenchProps | null) {
  const name = b ? headline(b) : null
  useEffect(() => {
    if (!name) return
    document.title = `${name} · Bench Finder`
    return () => {
      document.title = "Bench Finder"
    }
  }, [name])
}
