import "maplibre-gl/dist/maplibre-gl.css"
import {
  type GeoJSONSource,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"
import { useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { markerImage } from "../components/postmark/markerImage"
import { Rose } from "../components/postmark/Rose"
import { bestUrl, hasPhoto } from "../data/api"
import { isKnown, sectorOf } from "../data/facing"
import type { BenchFeature } from "../data/types"

// maplibre-gl 6 locates its worker next to its own module; once bundled that
// path no longer exists, so point it at the bundled worker explicitly.
setWorkerUrl(workerUrl)

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron"
const START_CENTER: [number, number] = [4.893, 52.3715]
const START_ZOOM = 13.1

export interface MapView {
  bounds: [number, number, number, number]
  center: [number, number]
}

interface Props {
  benches: BenchFeature[]
  visible: ReadonlySet<number>
  selectedId: number | null
  onSelect: (id: number) => void
  onView: (view: MapView) => void
  flyTo: { center: [number, number]; key: number } | null
}

interface MarkerHost {
  key: string
  el: HTMLElement
}
interface RoseHost extends MarkerHost {
  count: number
  label: string
  sectors: number[]
}

const SECTOR_PROPS = Object.fromEntries(
  [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [
    `s${i}`,
    ["+", ["case", ["==", ["get", "sec"], i], 1, 0]],
  ])
)

function unphotographed(benches: BenchFeature[], visible: ReadonlySet<number>) {
  return {
    type: "FeatureCollection" as const,
    features: benches
      .filter((b) => !hasPhoto(b) && visible.has(b.properties.id))
      .map((b) => ({
        type: "Feature" as const,
        geometry: b.geometry,
        properties: {
          id: b.properties.id,
          facing: b.properties.facing ?? 0,
          sec: sectorOf(b.properties.facing ?? 0),
          known: isKnown(b.properties),
        },
      })),
  }
}

function restyle(map: MapLibreMap) {
  for (const l of map.getStyle().layers) {
    if (l.type === "background") {
      map.setPaintProperty(l.id, "background-color", "#f6f6f1")
    }
    if (/water/.test(l.id) && l.type === "fill") {
      map.setPaintProperty(l.id, "fill-color", "#cfdbee")
    }
    if (/park|landuse|landcover|wood|grass/.test(l.id) && l.type === "fill") {
      map.setPaintProperty(l.id, "fill-color", "#e6eadc")
    }
    if (l.type === "symbol" && l.layout?.["text-field"]) {
      map.setPaintProperty(l.id, "text-color", "#5c5c57")
    }
  }
}

export default function BenchMap({
  benches,
  visible,
  selectedId,
  onSelect,
  onView,
  flyTo,
}: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)
  const [roses, setRoses] = useState<RoseHost[]>([])
  const roseMarkers = useRef(new Map<number, Marker>())
  const roseKey = useRef("")
  const thumbMarkers = useRef(new Map<number, Marker>())
  const [thumbHosts, setThumbHosts] = useState<MarkerHost[]>([])

  const cb = useRef({ onSelect, onView })
  cb.current = { onSelect, onView }
  const benchesRef = useRef(benches)
  benchesRef.current = benches
  const visibleRef = useRef(visible)
  visibleRef.current = visible

  const photographed = useMemo(() => benches.filter(hasPhoto), [benches])

  // Create the map once.
  useEffect(() => {
    if (!container.current) return
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE_URL,
      center: START_CENTER,
      zoom: START_ZOOM,
      attributionControl: { compact: true },
      dragRotate: false,
    })
    mapRef.current = map
    map.addControl(new NavigationControl({ showCompass: false }), "top-right")

    const reportView = () => {
      const b = map.getBounds()
      const c = map.getCenter()
      cb.current.onView({
        bounds: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
        center: [c.lng, c.lat],
      })
    }

    const syncRoses = () => {
      if (!map.getSource("benches") || !map.isSourceLoaded("benches")) return
      const seen = new Map<
        number,
        ReturnType<typeof map.querySourceFeatures>[number]
      >()
      for (const f of map.querySourceFeatures("benches", {
        filter: ["has", "point_count"],
      })) {
        const id = f.properties.cluster_id as number
        if (!seen.has(id)) seen.set(id, f)
      }
      const key = [...seen.keys()].sort((a, b) => a - b).join(",")
      if (key === roseKey.current) return
      roseKey.current = key
      for (const [id, m] of roseMarkers.current) {
        if (!seen.has(id)) {
          m.remove()
          roseMarkers.current.delete(id)
        }
      }
      for (const [id, f] of seen) {
        if (roseMarkers.current.has(id)) continue
        const el = document.createElement("div")
        el.className = "rose-wrap"
        const coords = (
          f.geometry as unknown as { coordinates: [number, number] }
        ).coordinates
        roseMarkers.current.set(
          id,
          new Marker({ element: el }).setLngLat(coords).addTo(map)
        )
      }
      setRoses(
        [...seen].map(([id, f]) => {
          const p = f.properties
          return {
            key: String(id),
            el: roseMarkers.current.get(id)?.getElement() as HTMLElement,
            count: p.point_count as number,
            label: String(p.point_count_abbreviated),
            sectors: [0, 1, 2, 3, 4, 5, 6, 7].map((i) => Number(p[`s${i}`])),
          }
        })
      )
    }

    map.on("load", () => {
      restyle(map)
      // Start the attribution collapsed behind its (i) button.
      map
        .getContainer()
        .querySelector(".maplibregl-ctrl-attrib")
        ?.classList.remove("maplibregl-compact-show")
      for (const k of ["known", "est", "sel"] as const) {
        map.addImage(`m-${k}`, markerImage(k), { pixelRatio: 2 })
      }
      map.addSource("benches", {
        type: "geojson",
        data: unphotographed(benchesRef.current, visibleRef.current),
        cluster: true,
        clusterRadius: 52,
        clusterMaxZoom: 13,
        clusterProperties: SECTOR_PROPS,
      })
      // Invisible so cluster features are queryable; drawn as postmark roses.
      map.addLayer({
        id: "clusters",
        type: "circle",
        source: "benches",
        filter: ["has", "point_count"],
        paint: { "circle-opacity": 0, "circle-radius": 1 },
      })
      map.addLayer({
        id: "bench",
        type: "symbol",
        source: "benches",
        filter: ["!", ["has", "point_count"]],
        layout: {
          "icon-image": ["case", ["get", "known"], "m-known", "m-est"],
          "icon-rotate": ["get", "facing"],
          "icon-rotation-alignment": "map",
          "icon-allow-overlap": true,
          "icon-size": 0.86,
        },
      })
      map.addSource("sel", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      })
      map.addLayer({
        id: "sel",
        type: "symbol",
        source: "sel",
        layout: {
          "icon-image": "m-sel",
          "icon-rotate": ["get", "facing"],
          "icon-rotation-alignment": "map",
          "icon-allow-overlap": true,
          "icon-size": 1.2,
        },
      })
      map.on("click", "bench", (e) => {
        const id = e.features?.[0]?.properties?.id
        if (typeof id === "number") cb.current.onSelect(id)
      })
      map.on("mouseenter", "bench", () => {
        map.getCanvas().style.cursor = "pointer"
      })
      map.on("mouseleave", "bench", () => {
        map.getCanvas().style.cursor = ""
      })
      map.on("moveend", reportView)
      map.on("render", syncRoses)
      reportView()
      setReady(true)
    })

    const roseRef = roseMarkers.current
    const thumbRef = thumbMarkers.current
    return () => {
      for (const m of roseRef.values()) m.remove()
      for (const m of thumbRef.values()) m.remove()
      roseRef.clear()
      thumbRef.clear()
      roseKey.current = ""
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  // Unphotographed benches follow the filters.
  useEffect(() => {
    if (!ready) return
    const src = mapRef.current?.getSource("benches") as
      | GeoJSONSource
      | undefined
    src?.setData(unphotographed(benches, visible))
  }, [ready, benches, visible])

  // Selected unphotographed bench.
  useEffect(() => {
    if (!ready) return
    const src = mapRef.current?.getSource("sel") as GeoJSONSource | undefined
    const b = benches.find((x) => x.properties.id === selectedId)
    src?.setData({
      type: "FeatureCollection",
      features:
        b && !hasPhoto(b)
          ? [
              {
                type: "Feature",
                geometry: b.geometry,
                properties: { facing: b.properties.facing ?? 0 },
              },
            ]
          : [],
    })
  }, [ready, benches, selectedId])

  // Photographed benches are tiny postcards (HTML markers rendered by React).
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const hosts: MarkerHost[] = []
    for (const b of photographed) {
      const id = b.properties.id
      let m = thumbMarkers.current.get(id)
      if (!m) {
        const el = document.createElement("div")
        el.className = "thumb-wrap"
        m = new Marker({ element: el, anchor: "bottom" })
          .setLngLat(b.geometry.coordinates)
          .addTo(map)
        thumbMarkers.current.set(id, m)
      }
      hosts.push({ key: String(id), el: m.getElement() })
    }
    setThumbHosts(hosts)
  }, [ready, photographed])

  useEffect(() => {
    if (flyTo) {
      mapRef.current?.flyTo({ center: flyTo.center, zoom: 15.5 })
    }
  }, [flyTo])

  const byKey = useMemo(
    () => new Map(photographed.map((b) => [String(b.properties.id), b])),
    [photographed]
  )

  return (
    <>
      <div
        ref={container}
        className="map-canvas"
        role="application"
        aria-label="Map of benches"
      />
      {thumbHosts.map(({ key, el }) => {
        const b = byKey.get(key)
        if (!b) return null
        const p = b.properties
        return createPortal(
          <button
            type="button"
            className="thumb"
            hidden={!visible.has(p.id)}
            data-sel={p.id === selectedId ? "" : undefined}
            aria-label={`Bench No. ${p.id} on ${p.address ?? "an unnamed path"}`}
            onClick={() => onSelect(p.id)}
          >
            <img src={bestUrl(p.hero_urls)} alt="" width={58} height={42} />
            <span
              className="needle"
              style={{ "--f": `${p.facing ?? 0}deg` } as React.CSSProperties}
            >
              <i />
            </span>
          </button>,
          el,
          key
        )
      })}
      {roses.map(({ key, el, count, label, sectors }) =>
        el
          ? createPortal(
              <button
                type="button"
                className="rose"
                aria-label={`${count} benches here; zoom in`}
                onClick={() => {
                  const m = mapRef.current
                  const ll = roseMarkers.current.get(Number(key))?.getLngLat()
                  if (m && ll) {
                    m.easeTo({ center: ll, zoom: m.getZoom() + 2 })
                  }
                }}
              >
                <Rose count={count} label={label} sectors={sectors} />
              </button>,
              el,
              key
            )
          : null
      )}
    </>
  )
}
