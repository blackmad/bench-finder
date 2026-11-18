import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useSearchParams } from "react-router-dom"
import { BenchPreview } from "../components/BenchPreview"
import { FiltersPanel } from "../components/FiltersPanel"
import { RailRow } from "../components/RailRow"
import { TopBar } from "../components/TopBar"
import { hasPhoto } from "../data/api"
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
import { benchCount, useBenches } from "../data/hooks"
import { buildRows } from "../data/rows"
import type { BenchFeature } from "../data/types"
import { setHere } from "../lib/here"
import { FAR_M, reachMetres } from "../lib/nearZoom"
import {
  type Viewport,
  viewportFromParams,
  viewportToParams,
} from "../lib/viewport"
import { type MapView, START_VIEW } from "../map/style"

const BenchMap = lazy(() => import("../map/BenchMap"))

const inBounds = (b: BenchFeature, v: MapView) => {
  const [w, s, e, n] = v.bounds
  const [lng, lat] = b.geometry.coordinates
  return lng >= w && lng <= e && lat >= s && lat <= n
}

const sameViewport = (a: Viewport, b: Viewport) =>
  Math.abs(a.lat - b.lat) < 5e-5 &&
  Math.abs(a.lng - b.lng) < 5e-5 &&
  Math.abs(a.z - b.z) < 0.02

// The area the data covers (Amsterdam): the start view only follows the
// visitor's location when it falls inside, [west, south, east, north].
const COVERED: [number, number, number, number] = [4.72, 52.27, 5.08, 52.44]
const covered = ([lng, lat]: [number, number]) =>
  lng >= COVERED[0] &&
  lng <= COVERED[2] &&
  lat >= COVERED[1] &&
  lat <= COVERED[3]

// A visitor who refused their location is not asked again on arrival (the
// Near me button still asks). Storage can be unavailable; then we just ask.
const GEO_DENIED_KEY = "bf:geo-denied"
const geoDenied = () => {
  try {
    return localStorage.getItem(GEO_DENIED_KEY) === "1"
  } catch {
    return false
  }
}
const rememberGeoDenied = (denied: boolean) => {
  try {
    if (denied) localStorage.setItem(GEO_DENIED_KEY, "1")
    else localStorage.removeItem(GEO_DENIED_KEY)
  } catch {
    // Private mode or blocked storage: nothing to remember.
  }
}

const sumBenches = (list: BenchFeature[]) =>
  list.reduce((s, b) => s + benchCount(b.properties), 0)

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
  // The bench opened in the rail, if any (`?bench=ID`).
  const openId = useMemo(() => {
    const n = Number(new URLSearchParams(spKey).get("bench"))
    return Number.isInteger(n) && n > 0 ? n : null
  }, [spKey])

  const [hoverId, setHoverId] = useState<number | null>(null)
  // A bench picked on the map leads the first row even if it is not nearest.
  const [mapPick, setMapPick] = useState<number | null>(null)
  const [view, setView] = useState<MapView | null>(null)
  const [flyTo, setFlyTo] = useState<{
    center: [number, number]
    key: number
    radiusM?: number
  } | null>(null)
  const [locating, setLocating] = useState<"idle" | "busy" | "denied" | "far">(
    "idle"
  )
  const railRef = useRef<HTMLElement>(null)

  const benches = useMemo(() => data ?? [], [data])
  const byId = useMemo(
    () => new Map(benches.map((b) => [b.properties.id, b])),
    [benches]
  )
  const selectedId = openId ?? hoverId

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

  const { rows, total, photographed, unfiltered } = useMemo(() => {
    const cx = view?.center[0] ?? START_VIEW.lng
    const cy = view?.center[1] ?? START_VIEW.lat
    const d = (b: BenchFeature) =>
      (b.geometry.coordinates[0] - cx) ** 2 * 0.37 +
      (b.geometry.coordinates[1] - cy) ** 2
    const here = (b: BenchFeature) => !view || inBounds(b, view)
    const vis = filtered.filter(here).sort((a, b) => d(a) - d(b))
    const photos = vis.filter(hasPhoto)
    const i = photos.findIndex((b) => b.properties.id === mapPick)
    if (i > 0) photos.unshift(...photos.splice(i, 1))
    return {
      rows: buildRows(photos),
      // Features are places; counts are of benches.
      total: sumBenches(vis),
      photographed: sumBenches(photos),
      unfiltered:
        filtered === benches
          ? sumBenches(vis)
          : sumBenches(benches.filter(here)),
    }
  }, [benches, filtered, view, mapPick])

  // Opening a bench adds a history entry, so Back returns to the rows.
  const openBench = useCallback(
    (id: number) => {
      setSp((prev) => {
        const next = new URLSearchParams(prev)
        next.set("bench", String(id))
        return next
      })
    },
    [setSp]
  )
  // Swiping an opened bench walks the benches nearest the middle of the map,
  // in the order the rail showed them when the bench was opened.
  const stepOrder = useRef<number[]>([])
  if (openId === null) {
    stepOrder.current = (rows[0]?.benches ?? []).map((f) => f.properties.id)
  }
  const stepBench = useCallback(
    (dir: 1 | -1) => {
      const ids = stepOrder.current
      const i = openId === null ? -1 : ids.indexOf(openId)
      const next = ids[i + dir]
      if (next !== undefined) openBench(next)
    },
    [openId, openBench]
  )
  const closeBench = useCallback(() => {
    const id = openId
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("bench")
      return next
    })
    // Back on the rows, keep the closed bench in sight.
    requestAnimationFrame(() => {
      railRef.current
        ?.querySelector<HTMLElement>(`[data-id="${id}"]`)
        ?.scrollIntoView({ block: "nearest", inline: "nearest" })
    })
  }, [setSp, openId])

  // A bench opened from a link may be off the map: bring it into view once.
  const shownOpen = useRef<number | null>(null)
  useEffect(() => {
    if (openId === null || !view || shownOpen.current === openId) return
    const b = byId.get(openId)
    if (!b) return
    shownOpen.current = openId
    if (!inBounds(b, view)) {
      setFlyTo({ center: b.geometry.coordinates, key: Date.now() })
    }
  }, [openId, view, byId])

  const selectFromMap = useCallback(
    (id: number) => {
      setMapPick(id)
      openBench(id)
    },
    [openBench]
  )

  const flyToPlace = useCallback((center: [number, number]) => {
    setFlyTo({ center, key: Date.now() })
  }, [])

  // Location: asked once on arrival (see below) and whenever the button is
  // pressed. `quiet` keeps the start view without a note when it fails.
  const nearMe = useCallback(
    (quiet = false) => {
      if (!navigator.geolocation) {
        setLocating(quiet ? "idle" : "denied")
        return
      }
      if (quiet && geoDenied()) return
      setLocating("busy")
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          rememberGeoDenied(false)
          const here: [number, number] = [
            pos.coords.longitude,
            pos.coords.latitude,
          ]
          // On arrival, only leave the start view for somewhere covered.
          if (quiet && !covered(here)) {
            setLocating("idle")
            return
          }
          // Reach out until about eight places are in view, however sparse.
          const pts = benches.map(
            (b) => b.geometry.coordinates as [number, number]
          )
          const radiusM = reachMetres(here, pts)
          if (reachMetres(here, pts, 1) > FAR_M) {
            setLocating(quiet ? "idle" : "far")
            return
          }
          setLocating("idle")
          setHere(here)
          setFlyTo({ center: here, key: Date.now(), radiusM })
        },
        (err) => {
          if (err.code === err.PERMISSION_DENIED) rememberGeoDenied(true)
          setLocating(quiet ? "idle" : "denied")
        },
        { timeout: 10_000, maximumAge: 60_000 }
      )
    },
    [benches]
  )

  // Default to "near me": a visit with no place or bench in the link starts
  // where the visitor is. The Amsterdam start view stays if they say no (and
  // they are not asked again on later visits) or are outside the covered area.
  const autoNear = useRef(urlViewport === null && openId === null)
  useEffect(() => {
    if (!autoNear.current || !data) return
    autoNear.current = false
    nearMe(true)
  }, [data, nearMe])

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
            onClick={() => nearMe()}
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
          ) : locating === "far" ? (
            <p className="nearme-note" role="status">
              No benches near you yet: Bench Finder covers Amsterdam for now.
            </p>
          ) : null}
        </div>
        <section className="rail" aria-label="Benches" ref={railRef}>
          {openId !== null && data ? (
            <BenchPreview
              key={openId}
              id={openId}
              bench={byId.get(openId)?.properties ?? null}
              onClose={closeBench}
              onStep={stepBench}
            />
          ) : (
            <>
              <RailCount
                state={isPending ? "loading" : error ? "error" : "ok"}
                total={total}
                photographed={photographed}
                unfiltered={unfiltered}
                filters={filters}
                onClear={() => setFilters(NO_FILTERS)}
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
                  grid
                  key={r.key}
                  row={r}
                  selectedId={selectedId}
                  onSelect={setHoverId}
                  onOpen={openBench}
                />
              ))}
            </>
          )}
        </section>
      </main>
    </>
  )
}

function RailCount({
  state,
  total,
  photographed,
  unfiltered,
  filters,
  onClear,
}: {
  state: "loading" | "error" | "ok"
  total: number
  photographed: number
  unfiltered: number
  filters: Filters
  onClear: () => void
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
  const photos =
    total > 0 ? (
      <>
        , <b className="num">{photographed.toLocaleString("en")}</b> with a
        photo
      </>
    ) : null
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
        <span>
          <b className="num">{total.toLocaleString("en")}</b>{" "}
          {total === 1 ? "bench" : "benches"} in view on the map
          {photos}
        </span>
      )}
    </p>
  )
}
