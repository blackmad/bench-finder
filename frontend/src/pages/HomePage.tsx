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
import { FiltersPanel } from "../components/FiltersPanel"
import { SlidersIcon } from "../components/Icons"
import { PlainRow, Postcard } from "../components/Postcard"
import { TopBar } from "../components/TopBar"
import { hasPhoto } from "../data/api"
import { useBenches } from "../data/hooks"
import type { BenchFeature } from "../data/types"
import {
  type Filters,
  filtersFromParams,
  filtersToParams,
  passes,
  type Viewport,
  viewportFromParams,
  viewportToParams,
} from "../lib/filters"
import { type MapView, START_VIEW } from "../map/BenchMap"

const BenchMap = lazy(() => import("../map/BenchMap"))

const MAX_PHOTOS = 60
const MAX_PLAIN = 24
const PHONE = "(max-width: 760px)"

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
  const filters = useMemo(
    () => filtersFromParams(new URLSearchParams(spKey)),
    [spKey]
  )
  const urlViewport = useMemo(
    () => viewportFromParams(new URLSearchParams(spKey)),
    [spKey]
  )
  const urlViewportRef = useRef(urlViewport)
  urlViewportRef.current = urlViewport
  const initialView = useRef(urlViewport ?? START_VIEW).current

  const [filtersOpen, setFiltersOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [view, setView] = useState<MapView | null>(null)
  const [flyTo, setFlyTo] = useState<{
    center: [number, number]
    key: number
  } | null>(null)
  const [locating, setLocating] = useState<"idle" | "busy" | "denied">("idle")
  const cardsRef = useRef<HTMLDivElement>(null)
  const programmaticScroll = useRef(0)

  const benches = useMemo(() => data ?? [], [data])
  const visible = useMemo(
    () =>
      new Set(
        benches
          .filter((b) => passes(b.properties, filters))
          .map((b) => b.properties.id)
      ),
    [benches, filters]
  )

  const setFilters = useCallback(
    (f: Filters) =>
      setSp((prev) => {
        const next = new URLSearchParams(prev)
        filtersToParams(f, next)
        return next
      }),
    [setSp]
  )

  // The viewport goes in the URL once a move ends. The first report, and any
  // report that already matches the URL (back/forward), do not add history.
  const onView = useCallback(
    (v: MapView) => {
      setView(v)
      const here: Viewport = {
        lat: v.center[1],
        lng: v.center[0],
        z: v.zoom,
      }
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

  const { photos, plain, total, inView } = useMemo(() => {
    const cx = view?.center[0] ?? START_VIEW.lng
    const cy = view?.center[1] ?? START_VIEW.lat
    const d = (b: BenchFeature) =>
      (b.geometry.coordinates[0] - cx) ** 2 * 0.37 +
      (b.geometry.coordinates[1] - cy) ** 2
    const vis = benches.filter(
      (b) => visible.has(b.properties.id) && (!view || inBounds(b, view))
    )
    const byDistance = (a: BenchFeature, b: BenchFeature) => d(a) - d(b)
    return {
      photos: vis.filter(hasPhoto).sort(byDistance).slice(0, MAX_PHOTOS),
      plain: vis
        .filter((b) => !hasPhoto(b))
        .sort(byDistance)
        .slice(0, MAX_PLAIN),
      total: vis.length,
      inView: new Set(vis.map((b) => b.properties.id)),
    }
  }, [benches, visible, view])

  // Keep a selection that is in view; default to the nearest postcard.
  useEffect(() => {
    if (selectedId !== null && inView.has(selectedId)) return
    if (photos[0]) setSelectedId(photos[0].properties.id)
  }, [photos, inView, selectedId])

  const scrollToCard = useCallback((id: number) => {
    programmaticScroll.current = Date.now()
    cardsRef.current?.querySelector(`[data-id="${id}"]`)?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    })
  }, [])

  const selectFromMap = useCallback(
    (id: number) => {
      setSelectedId(id)
      scrollToCard(id)
    },
    [scrollToCard]
  )

  // Phone: the card snapped to the centre is the selected bench. Ignore the
  // cards that sweep past while the stack scrolls to a map selection.
  // biome-ignore lint/correctness/useExhaustiveDependencies: re-observe when the card list changes
  useEffect(() => {
    const root = cardsRef.current
    if (!root || !window.matchMedia(PHONE).matches) return
    const io = new IntersectionObserver(
      (entries) => {
        if (Date.now() - programmaticScroll.current < 900) return
        for (const e of entries) {
          if (e.isIntersecting && e.intersectionRatio > 0.75) {
            setSelectedId(Number((e.target as HTMLElement).dataset.id))
          }
        }
      },
      { root, threshold: [0.75] }
    )
    for (const el of root.querySelectorAll(".postcard")) io.observe(el)
    return () => io.disconnect()
  }, [photos])

  useEffect(() => {
    if (!filtersOpen) return
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFiltersOpen(false)
    }
    document.addEventListener("keydown", esc)
    return () => document.removeEventListener("keydown", esc)
  }, [filtersOpen])

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

  const filterCount =
    filters.types.size + filters.faces.size + filters.sectors.size

  // DOM order is the keyboard path: filters, then the map, then the rack of
  // postcards (the only keyboard route to each bench; markers are GL-drawn).
  return (
    <>
      <TopBar onPlace={flyToPlace} />
      <main className="atlas" data-filters={filtersOpen ? "" : undefined}>
        <h1 className="sr">Benches by what they look at</h1>
        <button
          className="sheet-toggle"
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="filters"
          onClick={() => setFiltersOpen((o) => !o)}
        >
          <SlidersIcon />
          {filtersOpen ? "Close" : "Filters"}
          {filterCount > 0 ? (
            <span className="count num">
              {filterCount}
              <span className="sr"> active</span>
            </span>
          ) : null}
        </button>
        <FiltersPanel filters={filters} onChange={setFilters} />
        <div className="mapwrap">
          <Suspense fallback={null}>
            {data ? (
              <BenchMap
                benches={benches}
                visible={visible}
                selectedId={selectedId}
                onSelect={selectFromMap}
                onView={onView}
                initialView={initialView}
                viewport={urlViewport}
                flyTo={flyTo}
              />
            ) : null}
          </Suspense>
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
        <aside className="rack" aria-label="Benches in view">
          <div className="rackhead">
            <span role="status">
              <strong className="num">{total.toLocaleString("en")}</strong>{" "}
              benches in view
            </span>
            <span className="key">
              <span>
                <i />
                Mapped facing
              </span>
              <span>
                <i className="est" />
                Estimated
              </span>
            </span>
          </div>
          <div className="cards" ref={cardsRef}>
            {isPending ? (
              <p className="sectionnote">Loading benches...</p>
            ) : error ? (
              <p className="sectionnote" role="alert">
                Could not load the benches. Check your connection and reload.
              </p>
            ) : photos.length ? (
              photos.map((b) => (
                <Postcard
                  key={b.properties.id}
                  bench={b.properties}
                  selected={b.properties.id === selectedId}
                  onSelect={setSelectedId}
                />
              ))
            ) : (
              <p className="sectionnote">
                No photographed benches in this view yet. Zoom out, or loosen
                the filters.
              </p>
            )}
            {plain.length ? (
              <>
                <p
                  className="sectionnote caps"
                  style={{ fontSize: 11, margin: "6px 0 -10px" }}
                >
                  Not yet photographed
                </p>
                {plain.map((b) => (
                  <PlainRow key={b.properties.id} bench={b.properties} />
                ))}
              </>
            ) : null}
          </div>
        </aside>
      </main>
    </>
  )
}
