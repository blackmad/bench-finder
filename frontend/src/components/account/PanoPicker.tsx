import {
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react"
import {
  type CityPano,
  cityPanos,
  fractionOf,
  norm,
  offset,
  type PanoPick,
} from "../../lib/pano"

const STRIP_H = 200
/** Share of the panorama's height the strip shows at zoom 1 (around the horizon). */
const BAND = 0.55
const ZOOMS = [1, 1.6, 2.5, 4]
const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
const compass = (h: number) => COMPASS[Math.round(norm(h) / 45) % 8]

/**
 * The City of Amsterdam's street panoramas around `point`, as a strip you drag
 * until the bench sits under the centre line. Reports the panorama and the
 * heading under the line through `onChange`.
 */
export default function PanoPicker({
  point,
  onChange,
}: {
  point: { lat: number; lng: number }
  onChange: (p: PanoPick | null) => void
}) {
  const [panos, setPanos] = useState<CityPano[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const [zoom, setZoom] = useState(0)
  const [heading, setHeading] = useState(0)
  // Only a view the reporter turned or zoomed counts as pointing at the bench.
  const [aimed, setAimed] = useState(false)
  const turn: typeof setHeading = (v) => {
    setAimed(true)
    setHeading(v)
  }
  const [width, setWidth] = useState(480)
  const box = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; heading: number } | null>(null)
  const cb = useRef(onChange)
  cb.current = onChange

  // Panoramas near the pin (refetched when the pin moves far enough to matter).
  const key = `${point.lat.toFixed(4)},${point.lng.toFixed(4)}`
  // biome-ignore lint/correctness/useExhaustiveDependencies: refetch only per ~10 m cell
  useEffect(() => {
    const ac = new AbortController()
    setPanos(null)
    setError(null)
    cityPanos(point, 60, ac.signal)
      .then((ps) => {
        setPanos(ps)
        setIndex(0)
      })
      .catch((e) => {
        if (!ac.signal.aborted) {
          setError(e instanceof Error ? e.message : "Could not load panoramas")
        }
      })
    return () => ac.abort()
  }, [key])

  const pano = panos?.[index] ?? null

  // Aim at the pin whenever the panorama changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: only on a new panorama
  useEffect(() => {
    if (pano) setHeading(offset(pano, point).bearing)
  }, [pano?.id])

  useEffect(() => {
    cb.current(
      pano && (aimed || zoom > 0)
        ? {
            source: "amsterdam",
            id: pano.id,
            heading: Math.round(norm(heading) * 10) / 10,
          }
        : null
    )
  }, [pano, heading, aimed, zoom])

  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  if (error) {
    return (
      <p className="form-error" role="alert">
        {error}
      </p>
    )
  }
  if (!panos) return <p className="form-note">Looking for panoramas…</p>
  if (!pano) {
    return (
      <p className="form-note">
        No city panoramas within 60 m of the pin. Move the pin nearer a street,
        or paste a Street View link below.
      </p>
    )
  }

  const z = ZOOMS[zoom]
  const imgH = (STRIP_H / BAND) * z
  const imgW = imgH * 2
  const top = -(imgH - STRIP_H) / 2
  // Left edge of the copy whose column under the centre line is `heading`.
  const x0 = width / 2 - fractionOf(heading) * imgW
  const lefts = [-1, 0, 1, 2].map(
    (k) => (((x0 % imgW) + imgW) % imgW) - imgW + k * imgW
  )
  const src =
    z > 1.5 ? pano.image.replace("panorama_2000", "panorama_4000") : pano.image
  const degPerPx = 360 / imgW

  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    drag.current = { x: e.clientX, heading }
  }
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    turn(norm(drag.current.heading - (e.clientX - drag.current.x) * degPerPx))
  }
  const onUp = () => {
    drag.current = null
  }
  // Double-click: turn to that spot and zoom in a step (from the closest, back out).
  const onDouble = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    turn(norm(heading + (e.clientX - r.left - width / 2) * degPerPx))
    setZoom((n) => (n + 1) % ZOOMS.length)
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 15 : 3
    if (e.key === "ArrowLeft") turn((h) => norm(h - step))
    else if (e.key === "ArrowRight") turn((h) => norm(h + step))
    else if (e.key === "+" || e.key === "=")
      setZoom((n) => Math.min(n + 1, ZOOMS.length - 1))
    else if (e.key === "-") setZoom((n) => Math.max(n - 1, 0))
    else return
    e.preventDefault()
  }

  return (
    <div className="panopick stack">
      <div
        ref={box}
        className="panostrip"
        style={{ height: STRIP_H }}
        role="slider"
        tabIndex={0}
        aria-label="Turn the panorama until the bench is under the line"
        aria-valuemin={0}
        aria-valuemax={359}
        aria-valuenow={Math.round(heading)}
        aria-valuetext={`Looking ${compass(heading)}, ${Math.round(heading)} degrees`}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        onDoubleClick={onDouble}
        onKeyDown={onKey}
      >
        {lefts.map((l) => (
          <img
            key={l}
            src={src}
            alt=""
            draggable={false}
            style={{ left: l, top, width: imgW, height: imgH }}
          />
        ))}
        <span className="panoline" aria-hidden="true" />
        <span className="panohead num" aria-hidden="true">
          {compass(heading)} {Math.round(heading)}°
        </span>
      </div>
      <div className="row panoctl">
        <button
          type="button"
          className="btn"
          onClick={() => turn((h) => norm(h - 10))}
          aria-label="Turn left"
        >
          ←
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => turn((h) => norm(h + 10))}
          aria-label="Turn right"
        >
          →
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => setZoom((n) => Math.min(n + 1, ZOOMS.length - 1))}
          disabled={zoom === ZOOMS.length - 1}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => setZoom((n) => Math.max(n - 1, 0))}
          disabled={zoom === 0}
          aria-label="Zoom out"
        >
          −
        </button>
        <span className="panometa">
          <span className="num">
            {Math.round(pano.distance)} m from the pin · {pano.date.slice(0, 7)}
          </span>
          {panos.length > 1 ? (
            <>
              {" · "}
              <button
                type="button"
                className="linkbtn"
                onClick={() => setIndex((i) => (i + 1) % panos.length)}
              >
                Another panorama ({index + 1} of {panos.length})
              </button>
            </>
          ) : null}
        </span>
      </div>
      <p className="form-note">
        Drag the picture (or use the arrows) until the bench is under the red
        line; double-click to zoom in there. City of Amsterdam panoramas.
      </p>
    </div>
  )
}
