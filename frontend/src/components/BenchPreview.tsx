import { useEffect, useId, useRef, useState } from "react"
import { focusStyle } from "../data/api"
import { headline, heroImage, lede, monthYear } from "../data/describe"
import { useHeroPicks } from "../data/heroes"
import { useBench } from "../data/hooks"
import { streetViewTarget } from "../data/streetView"
import type { BenchDetail, BenchProps } from "../data/types"
import { useSwipe } from "../lib/useSwipe"
import { Away } from "./Away"
import {
  BenchActions,
  BenchNotes,
  BenchScore,
  ReportRow,
} from "./account/BenchSocial"
import { FindView } from "./account/FindView"
import { ClearHero, HeroButton } from "./account/HeroButton"
import { VisitorPhotos } from "./account/VisitorPhotos"
import { Facts, ViewFromBench } from "./BenchDetails"
import { BenchOutline } from "./BenchOutline"
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
 * rating, the notes, the other views, Street View and the report link. The map stays beside
 * it with the bench marked in vermilion; the URL carries `?bench=ID`.
 */
export function BenchPreview({ bench, id, onClose, onStep }: Props) {
  const swipe = useSwipe(onStep)
  const { data: detail, isPending } = useBench(id)
  const b: BenchProps | null = detail ?? bench
  const titleId = useId()
  const ref = useRef<HTMLElement>(null)
  const photo = useRef<HTMLDivElement>(null)
  const [viewing, setViewing] = useState<number | null>(null)
  const { data: picks } = useHeroPicks()

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
      <div className="ph" ref={photo}>
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
        {detail?.hero_outline && b.hero_urls ? (
          <BenchOutline
            box={photo}
            outline={detail.hero_outline}
            width={b.hero_width ?? 800}
            height={b.hero_height ?? 800}
            focus={b.hero_focus}
          />
        ) : null}
        <Away lat={b.lat} lng={b.lng} />
      </div>
      {picks?.[b.id] ? <ClearHero benchId={b.id} /> : null}
      <div className="titlecard">
        <h2 id={titleId} tabIndex={-1}>
          {name}
        </h2>
        <BenchScore benchId={b.id} />
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
      <BenchNotes benchId={b.id} />
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
                action={<HeroButton benchId={b.id} image={g} />}
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
      <VisitorPhotos benchId={b.id} />
      <StreetView bench={detail} name={name} />
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
  const [finding, setFinding] = useState(false)
  const target = d ? streetViewTarget(d) : null
  if (!d || !target) return null
  return (
    <>
      <ViewFromBench target={target} facing={d.facing} street={name} />
      <p className="findviewbtn">
        <button
          type="button"
          className="linkbtn"
          onClick={() => setFinding(true)}
        >
          Find a better view of this bench in Street View
        </button>
      </p>
      {finding ? (
        <FindView
          benchId={d.id}
          target={target}
          onClose={() => setFinding(false)}
        />
      ) : null}
    </>
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
