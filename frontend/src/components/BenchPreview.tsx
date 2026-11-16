import { useEffect, useId, useRef } from "react"
import { Link } from "react-router-dom"
import { cityName, headline, heroImage, lede, seatText } from "../data/describe"
import { looksAt } from "../data/facing"
import { useBench } from "../data/hooks"
import type { BenchProps } from "../data/types"
import { PinIcon } from "./Icons"
import { Photo } from "./Photo"
import { Seal } from "./Seal"
import { ViewFigure } from "./ViewFigure"

interface Props {
  /** The bench's map properties, when the GeoJSON has it (renders at once). */
  bench: BenchProps | null
  id: number
  onClose: () => void
}

/**
 * A bench opened in the rail: its photo large, the title card, what it looks
 * at, the other views, and the way on to the full page. The map stays beside
 * it with the bench marked in vermilion; the URL carries `?bench=ID`.
 */
export function BenchPreview({ bench, id, onClose }: Props) {
  const { data: detail, isPending } = useBench(id)
  const b: BenchProps | null = detail ?? bench
  const titleId = useId()
  const ref = useRef<HTMLElement>(null)

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

  if (!b) {
    return (
      <section className="pv" ref={ref} aria-labelledby={titleId}>
        {back}
        <h2 id={titleId} className="railnote" tabIndex={-1}>
          {isPending ? "Loading bench…" : `Bench No. ${id} could not be found.`}
        </h2>
      </section>
    )
  }

  const name = headline(b)
  const city = detail ? cityName(detail) : null
  const looks = looksAt(b.faces_category)
  const seat = seatText(b.backrest)
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
            decoding="async"
          />
        ) : (
          <p className="nophoto">No street-level photo of this bench yet.</p>
        )}
        <span className="sealslot">
          <Seal bench={b} size={56} selected />
        </span>
      </div>
      <div className="titlecard">
        <p className="kicker caps">
          Bench No. {b.id}
          {city ? ` · ${city}` : ""}
        </p>
        {/* The title is the way to the rest (notes, ratings, the panorama);
            there is no separate "open the page" button. */}
        <h2 id={titleId} tabIndex={-1}>
          <Link className="titlelink" to={`/bench/${b.id}`}>
            {name}
          </Link>
        </h2>
        <p className="lede">{detail ? lede(detail) : " "}</p>
        <p className="facts">
          {looks || detail?.faces_text ? (
            <span>
              <b>{looks ?? detail?.faces_text}</b>
            </span>
          ) : null}
          {seat ? (
            <span>
              <b>{seat}</b>
            </span>
          ) : null}
          {b.material ? (
            <span>
              <b>{b.material.replace(/^\w/, (c) => c.toUpperCase())}</b>
            </span>
          ) : null}
        </p>
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
            {views.map((g) => (
              <ViewFigure
                key={Object.values(g.urls)[0]}
                image={g}
                name={name}
                sizes="(max-width: 760px) 60vw, 220px"
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}
