import { lazy, Suspense, useCallback, useMemo, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { BenchOfTheDay } from "../components/BenchOfTheDay"
import { FiltersPanel } from "../components/FiltersPanel"
import { RailRow } from "../components/RailRow"
import { TopBar } from "../components/TopBar"
import { hasPhoto } from "../data/api"
import { headline } from "../data/describe"
import { facingKind, facingShort } from "../data/facing"
import {
  coverage as coverageOf,
  type Filters,
  filtersFromParams,
  filtersToParams,
  isFiltered,
  NO_FILTERS,
  offered as offeredBy,
  optionCounts,
  passes,
  summary,
} from "../data/filters"
import { useBenches } from "../data/hooks"
import { benchOfTheDay, buildRows } from "../data/rows"
import type { BenchFeature } from "../data/types"
import {
  type Viewport,
  viewportFromParams,
  viewportToParams,
} from "../lib/viewport"
import { type MapView, START_VIEW } from "../map/style"

const BenchMap = lazy(() => import("../map/BenchMap"))

const MAX_PLAIN = 12

const inBounds = (b: BenchFeature, v: MapView) => {
  const [w, s, e, n] = v.bounds
  const [lng, lat] = b.geometry.coordinates
  return lng >= w && lng <= e && lat >= s && lat <= n
}

const sameViewport = (a: Viewport, b: Viewport) =>
  Math.abs(a.lat - b.lat) < 5e-5 &&
  Math.abs(a.lng - b.lng) < 5e-5 &&
  Math.abs(a.z - b.z) < 0.02

export default function HomePage() {
  const { data, isPending, error } = useBenches()
  const [sp, setSp] = useSearchParams()
  const spKey = sp.toString()
  const urlViewport = useMemo(
    () => viewportFromParams(new URLSearchParams(spKey)),
    [spKey]
  )
  const urlViewportRef = useRef(urlViewport)
  urlViewportRef.current = urlViewport
  const initialView = useRef(urlViewport ?? START_VIEW).current

  const [selectedId, setSelectedId] = useState<number | null>(null)
  // A bench picked on the map leads the first row even if it is not nearest.
  const [mapPick, setMapPick] = useState<number | null>(null)
  const [view, setView] = useState<MapView | null>(null)
  const [flyTo, setFlyTo] = useState<{
    center: [number, number]
    key: number
  } | null>(null)
  const [locating, setLocating] = useState<"idle" | "busy" | "denied">("idle")
  const railRef = useRef<HTMLElement>(null)

  const benches = useMemo(() => data ?? [], [data])
  // The bench of the day ignores the filters: it is the same for everyone
  // that day, a postcard rather than a search result.
  const hero = useMemo(() => benchOfTheDay(benches), [benches])

  const filters = useMemo(
    () => filtersFromParams(new URLSearchParams(spKey)),
    [spKey]
  )
  const setFilters = useCallback(
    (f: Filters) =>
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          filtersToParams(f, next)
          return next
        },
        { replace: true }
      ),
    [setSp]
  )
  const coverage = useMemo(() => coverageOf(benches), [benches])
  const offered = useMemo(() => offeredBy(coverage), [coverage])
  const counts = useMemo(
    () => optionCounts(benches, filters),
    [benches, filters]
  )
  const filtered = useMemo(
    () =>
      isFiltered(filters)
        ? benches.filter((b) => passes(b.properties, filters))
        : benches,
    [benches, filters]
  )
  const filteredIds = useMemo(
    () => new Set(filtered.map((b) => b.properties.id)),
    [filtered]
  )
  const hasEstimated = useMemo(
    () => benches.some((b) => facingKind(b.properties) === "estimated"),
    [benches]
  )

  // The viewport goes in the URL once a move ends. The first report, and any
  // report that already matches the URL (back/forward), do not add history.
  const onView = useCallback(
    (v: MapView) => {
      setView(v)
      const here: Viewport = { lat: v.center[1], lng: v.center[0], z: v.zoom }
      const known = urlViewportRef.current
      if (known && sameViewport(known, here)) return
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          viewportToParams(here, next)
          return next
        },
        { replace: !known }
      )
    },
    [setSp]
  )

  const { rows, plain, total, unfiltered } = useMemo(() => {
    const cx = view?.center[0] ?? START_VIEW.lng
    const cy = view?.center[1] ?? START_VIEW.lat
    const d = (b: BenchFeature) =>
      (b.geometry.coordinates[0] - cx) ** 2 * 0.37 +
      (b.geometry.coordinates[1] - cy) ** 2
    const here = (b: BenchFeature) => !view || inBounds(b, view)
    const vis = filtered.filter(here).sort((a, b) => d(a) - d(b))
    const photos = vis.filter(hasPhoto)
    const plain = vis.filter((b) => !hasPhoto(b))
    for (const list of [photos, plain]) {
      const i = list.findIndex((b) => b.properties.id === mapPick)
      if (i > 0) list.unshift(...list.splice(i, 1))
    }
    return {
      rows: buildRows(photos, filtered !== benches),
      plain,
      total: vis.length,
      unfiltered:
        filtered === benches ? vis.length : benches.filter(here).length,
    }
  }, [benches, filtered, view, mapPick])

  const selectFromMap = useCallback((id: number) => {
    setSelectedId(id)
    setMapPick(id)
    // After the rows re-render with the pick leading the first one.
    requestAnimationFrame(() => {
      railRef.current?.querySelector(`[data-id="${id}"]`)?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "start",
      })
    })
  }, [])

  const flyToPlace = useCallback((center: [number, number]) => {
    setFlyTo({ center, key: Date.now() })
  }, [])

  // Location is only requested when the button is pressed.
  const nearMe = useCallback(() => {
    if (!navigator.geolocation) {
      setLocating("denied")
      return
    }
    setLocating("busy")
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating("idle")
        flyToPlace([pos.coords.longitude, pos.coords.latitude])
      },
      () => setLocating("denied"),
      { timeout: 10_000, maximumAge: 60_000 }
    )
  }, [flyToPlace])

  // DOM order is the keyboard path: the map, then the rail (the keyboard
  // route to each bench; markers are GL-drawn).
  return (
    <>
      <TopBar onPlace={flyToPlace} />
      <main className="atlas">
        <h1 className="sr">Bench Finder: benches and the view from each</h1>
        <div className="mapwrap">
          <Suspense fallback={null}>
            {data ? (
              <BenchMap
                benches={benches}
                visible={filteredIds}
                selectedId={selectedId}
                onSelect={selectFromMap}
                onView={onView}
                initialView={initialView}
                viewport={urlViewport}
                flyTo={flyTo}
              />
            ) : null}
          </Suspense>
          {data ? (
            <FiltersPanel
              filters={filters}
              onChange={setFilters}
              coverage={coverage}
              offered={offered}
              counts={counts}
              matching={filtered.length}
              matchingInView={total}
            />
          ) : null}
          <button
            className="nearme"
            type="button"
            onClick={nearMe}
            disabled={locating === "busy"}
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="3.2" />
              <circle cx="12" cy="12" r="7.5" />
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
            </svg>
            {locating === "busy" ? "Locating…" : "Near me"}
          </button>
          {locating === "denied" ? (
            <p className="nearme-note" role="status">
              Location is unavailable. Search for a place instead.
            </p>
          ) : null}
        </div>
        <section className="rail" aria-label="Benches" ref={railRef}>
          {hero ? <BenchOfTheDay bench={hero.properties} /> : null}
          <RailCount
            state={isPending ? "loading" : error ? "error" : "ok"}
            total={total}
            unfiltered={unfiltered}
            filters={filters}
            onClear={() => setFilters(NO_FILTERS)}
            hasEstimated={hasEstimated}
          />
          {data && !rows.length ? (
            <p className="railnote">
              {isFiltered(filters)
                ? "No photographed benches here match the filters. Zoom out, move the map or loosen the filters."
                : "No photographed benches in this part of the map. Zoom out or move the map."}
            </p>
          ) : null}
          {rows.map((r) => (
            <RailRow
              key={r.key}
              row={r}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          ))}
          <PlainList benches={plain} selectedId={selectedId} />
        </section>
      </main>
    </>
  )
}

function RailCount({
  state,
  total,
  unfiltered,
  filters,
  onClear,
  hasEstimated,
}: {
  state: "loading" | "error" | "ok"
  total: number
  unfiltered: number
  filters: Filters
  onClear: () => void
  hasEstimated: boolean
}) {
  if (state !== "ok") {
    return (
      <p className="railcount" role="status">
        {state === "loading"
          ? "Loading benches…"
          : "Could not load the benches. Check your connection and reload."}
      </p>
    )
  }
  return (
    <p className="railcount" role="status">
      {isFiltered(filters) ? (
        <span className="filtered">
          <b className="num">{total.toLocaleString("en")}</b> of{" "}
          <span className="num">{unfiltered.toLocaleString("en")}</span> benches
          in view: {summary(filters)}.{" "}
          <button type="button" className="linkbtn" onClick={onClear}>
            Clear filters
          </button>
        </span>
      ) : (
        <>
          <b className="num">{total.toLocaleString("en")}</b>{" "}
          {total === 1 ? "bench" : "benches"} in view on the map
        </>
      )}
      <span className="key">
        <span>
          <i />
          Facing mapped
        </span>
        {hasEstimated ? (
          <span>
            <i className="est" />
            Estimated
          </span>
        ) : null}
        <span>
          <i className="none" />
          Facing not known
        </span>
      </span>
    </p>
  )
}

/** Unphotographed benches in view: a plain list, honest about the missing photo. */
function PlainList({
  benches,
  selectedId,
}: {
  benches: BenchFeature[]
  selectedId: number | null
}) {
  if (!benches.length) return null
  return (
    <section className="plainrow" aria-labelledby="h-plain">
      <div className="rowhead">
        <h3 id="h-plain" className="caps">
          Not photographed yet
        </h3>
        <small className="num">
          {benches.length.toLocaleString("en")} in view
          {benches.length > MAX_PLAIN ? `, nearest ${MAX_PLAIN}` : ""}
        </small>
      </div>
      <ul>
        {benches.slice(0, MAX_PLAIN).map((b) => {
          const f = facingShort(b.properties)
          return (
            <li key={b.properties.id}>
              <Link
                to={`/bench/${b.properties.id}`}
                data-id={b.properties.id}
                aria-current={
                  b.properties.id === selectedId ? "true" : undefined
                }
              >
                <span className="caps">{headline(b.properties)}</span>
                <small>{f ? `Faces ${f}` : "No photo yet"}</small>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
