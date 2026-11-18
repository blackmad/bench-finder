import { useEffect, useId, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { focusStyle } from "../data/api"
import { headline, heroImage, lede } from "../data/describe"
import { useBench } from "../data/hooks"
import type { BenchProps } from "../data/types"
import { useSwipe } from "../lib/useSwipe"
import { Away } from "./Away"
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
 * A bench opened in the rail: its photo large, the title card, what it looks
 * at, the other views, and the way on to the full page. The map stays beside
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
        {/* The title is the way to the rest (notes, ratings, the panorama);
            there is no separate "open the page" button. */}
        <h2 id={titleId} tabIndex={-1}>
          <Link className="titlelink" to={`/bench/${b.id}`}>
            {name}
          </Link>
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
    </section>
  )
}
