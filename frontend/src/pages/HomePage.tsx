import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { FiltersPanel } from "../components/FiltersPanel"
import { SlidersIcon } from "../components/Icons"
import { PlainRow, Postcard } from "../components/Postcard"
import { TopBar } from "../components/TopBar"
import { hasPhoto } from "../data/api"
import { useBenches } from "../data/hooks"
import type { BenchFeature } from "../data/types"
import { type Filters, NO_FILTERS, passes } from "../lib/filters"
import type { MapView } from "../map/BenchMap"

const BenchMap = lazy(() => import("../map/BenchMap"))

const START_CENTER: [number, number] = [4.893, 52.3715]
const MAX_PLAIN = 24
const PHONE = "(max-width: 760px)"

interface PlaceResult {
  features?: { geometry: { coordinates: [number, number] } }[]
}

async function findPlace(q: string): Promise<[number, number] | null> {
  const res = await fetch(
    `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&lat=52.37&lon=4.89&limit=1`
  )
  if (!res.ok) return null
  const data = (await res.json()) as PlaceResult
  return data.features?.[0]?.geometry.coordinates ?? null
}

const inBounds = (b: BenchFeature, v: MapView) => {
  const [w, s, e, n] = v.bounds
  const [lng, lat] = b.geometry.coordinates
  return lng >= w && lng <= e && lat >= s && lat <= n
}

export default function HomePage() {
  const { data, isPending, error } = useBenches()
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [view, setView] = useState<MapView | null>(null)
  const [flyTo, setFlyTo] = useState<{
    center: [number, number]
    key: number
  } | null>(null)
  const cardsRef = useRef<HTMLDivElement>(null)

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

  const { photos, plain, total } = useMemo(() => {
    const [cx, cy] = view?.center ?? START_CENTER
    const d = (b: BenchFeature) =>
      (b.geometry.coordinates[0] - cx) ** 2 * 0.37 +
      (b.geometry.coordinates[1] - cy) ** 2
    const vis = benches.filter(
      (b) => visible.has(b.properties.id) && (!view || inBounds(b, view))
    )
    const byDistance = (a: BenchFeature, b: BenchFeature) => d(a) - d(b)
    return {
      photos: vis.filter(hasPhoto).sort(byDistance),
      plain: vis
        .filter((b) => !hasPhoto(b))
        .sort(byDistance)
        .slice(0, MAX_PLAIN),
      total: vis.length,
    }
  }, [benches, visible, view])

  // Keep a selection that is on the rack.
  useEffect(() => {
    if (!photos.some((b) => b.properties.id === selectedId) && photos[0]) {
      setSelectedId(photos[0].properties.id)
    }
  }, [photos, selectedId])

  const scrollToCard = useCallback((id: number) => {
    cardsRef.current
      ?.querySelector(`.postcard[data-id="${id}"]`)
      ?.scrollIntoView({
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

  // Phone: the card snapped to the centre is the selected bench.
  // biome-ignore lint/correctness/useExhaustiveDependencies: re-observe when the card list changes
  useEffect(() => {
    const root = cardsRef.current
    if (!root || !window.matchMedia(PHONE).matches) return
    const io = new IntersectionObserver(
      (entries) => {
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

  const search = useCallback(async (q: string) => {
    try {
      const center = await findPlace(q)
      if (center) setFlyTo({ center, key: Date.now() })
    } catch {
      // Search is best effort; the map stays where it was.
    }
  }, [])

  return (
    <>
      <TopBar onSearch={search} />
      <main className="atlas" data-filters={filtersOpen ? "" : undefined}>
        <div className="mapwrap">
          <Suspense fallback={null}>
            {data ? (
              <BenchMap
                benches={benches}
                visible={visible}
                selectedId={selectedId}
                onSelect={selectFromMap}
                onView={setView}
                flyTo={flyTo}
              />
            ) : null}
          </Suspense>
        </div>
        <aside className="rack" aria-label="Benches in view">
          <FiltersPanel filters={filters} onChange={setFilters} />
          <div className="rackhead">
            <span>
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
          <div className="cards" ref={cardsRef} aria-live="polite">
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
        <button
          className="sheet-toggle"
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="filters"
          onClick={() => setFiltersOpen((o) => !o)}
        >
          <SlidersIcon />
          Filters
        </button>
      </main>
    </>
  )
}
