import "maplibre-gl/dist/maplibre-gl.css"
import {
  type ExpressionSpecification,
  type GeoJSONSource,
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"
import { useEffect, useMemo, useRef, useState } from "react"
import { dataUrl, hasPhoto } from "../data/api"
import { isKnown, sectorOf } from "../data/facing"
import type { BenchFeature, ImageUrls } from "../data/types"
import type { Viewport } from "../lib/filters"
import { dotSprite, roseSprite, type Sprite, thumbSprite } from "./sprites"

// maplibre-gl 6 locates its worker next to its own module; once bundled that
// path no longer exists, so point it at the bundled worker explicitly.
setWorkerUrl(workerUrl)

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron"
export const START_VIEW: Viewport = { lat: 52.3715, lng: 4.893, z: 12.6 }

export interface MapView {
  bounds: [number, number, number, number]
  center: [number, number]
  zoom: number
}

interface Props {
  benches: BenchFeature[]
  visible: ReadonlySet<number>
  selectedId: number | null
  onSelect: (id: number) => void
  onView: (view: MapView) => void
  /** Where the map starts (from the URL, else the Amsterdam default). */
  initialView: Viewport
  /** The URL's viewport; the map jumps there when it differs (back/forward). */
  viewport: Viewport | null
  flyTo: { center: [number, number]; key: number } | null
}

const sectorExpr = (i: number): ExpressionSpecification => [
  "+",
  ["case", ["==", ["get", "sec"], i], 1, 0],
]
const SECTOR_PROPS = Object.fromEntries(
  [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [`s${i}`, sectorExpr(i)])
)

// Share of each facing sector in tenths, rounded up so any member shows a tick.
const levelExpr = (i: number): ExpressionSpecification => [
  "to-string",
  ["ceil", ["*", ["/", ["get", `s${i}`], ["get", "point_count"]], 10]],
]
const ROSE_IMAGE: ExpressionSpecification = [
  "concat",
  "rose:",
  ["step", ["get", "point_count"], "0", 20, "1", 100, "2"],
  ":",
  ["get", "point_count_abbreviated"],
  ":",
  ...[0, 1, 2, 3, 4, 5, 6, 7].flatMap((i) => [levelExpr(i), i < 7 ? "," : ""]),
]

const empty = { type: "FeatureCollection" as const, features: [] }

function dots(benches: BenchFeature[], visible: ReadonlySet<number>) {
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

function photos(benches: BenchFeature[], visible: ReadonlySet<number>) {
  return {
    type: "FeatureCollection" as const,
    features: benches
      .filter((b) => hasPhoto(b) && visible.has(b.properties.id))
      .map((b) => ({
        type: "Feature" as const,
        geometry: b.geometry,
        properties: { id: b.properties.id },
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

/** Smallest rendition that still covers a 2x thumbnail, else the widest. */
function thumbUrl(urls: ImageUrls): string {
  const widths = Object.keys(urls)
    .map(Number)
    .sort((a, b) => a - b)
  const w = widths.find((x) => x >= 116) ?? widths[widths.length - 1]
  return dataUrl(urls[String(w)])
}

const sameView = (a: Viewport, b: Viewport) =>
  Math.abs(a.lat - b.lat) < 5e-5 &&
  Math.abs(a.lng - b.lng) < 5e-5 &&
  Math.abs(a.z - b.z) < 0.02

export default function BenchMap({
  benches,
  visible,
  selectedId,
  onSelect,
  onView,
  initialView,
  viewport,
  flyTo,
}: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)

  const cb = useRef({ onSelect, onView })
  cb.current = { onSelect, onView }
  const benchesRef = useRef(benches)
  benchesRef.current = benches
  const visibleRef = useRef(visible)
  visibleRef.current = visible
  const initialRef = useRef(initialView)
  const byId = useMemo(
    () => new Map(benches.map((b) => [b.properties.id, b])),
    [benches]
  )
  const byIdRef = useRef(byId)
  byIdRef.current = byId

  // Create the map once.
  useEffect(() => {
    if (!container.current) return
    const start = initialRef.current
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE_URL,
      center: [start.lng, start.lat],
      zoom: start.z,
      attributionControl: { compact: true },
      dragRotate: false,
      maxPitch: 0,
    })
    mapRef.current = map
    // Test hook for the perf script: `/?debug=1` exposes the map instance.
    if (new URLSearchParams(location.search).has("debug")) {
      ;(window as unknown as { __map?: MapLibreMap }).__map = map
    }
    map.touchZoomRotate.disableRotation()
    map.addControl(new NavigationControl({ showCompass: false }), "top-right")

    // Sprites are drawn on demand: one cluster rose per (size, count, sector
    // pattern), one thumbnail per photographed bench.
    const made = new Set<string>()
    const photoCache = new Map<number, HTMLImageElement>()
    const queue: number[] = []
    let inflight = 0
    const add = (id: string, s: Sprite) => {
      if (map.hasImage(id)) map.updateImage(id, s.data)
      else map.addImage(id, s.data, { pixelRatio: s.pixelRatio })
    }
    const thumbArgs = (id: number, selected: boolean) => {
      const p = byIdRef.current.get(id)?.properties
      return {
        photo: photoCache.get(id) ?? null,
        facing: p?.facing ?? null,
        known: p ? isKnown(p) : false,
        selected,
      }
    }
    const drawThumb = (id: number) => {
      add(`thumb:${id}`, thumbSprite(thumbArgs(id, false)))
      const sel = `thumbsel:${id}`
      if (map.hasImage(sel)) add(sel, thumbSprite(thumbArgs(id, true)))
    }
    // Warm the thumbnails of the photographed benches nearest the start view
    // once, so panning around the city does not fetch images.
    const prefetch = () => {
      const cx = start.lng
      const cy = start.lat
      const near = benchesRef.current
        .filter(hasPhoto)
        .sort(
          (a, b) =>
            (a.geometry.coordinates[0] - cx) ** 2 * 0.37 +
            (a.geometry.coordinates[1] - cy) ** 2 -
            ((b.geometry.coordinates[0] - cx) ** 2 * 0.37 +
              (b.geometry.coordinates[1] - cy) ** 2)
        )
        .slice(0, 300)
      for (const b of near) queue.push(b.properties.id)
      pump()
    }
    const pump = () => {
      while (inflight < 6 && queue.length) {
        const id = queue.shift() as number
        // WebP decodes everywhere canvas does; fall back to AVIF in the dev fixture.
        const p = byIdRef.current.get(id)?.properties
        const urls = p?.hero_urls_webp ?? p?.hero_urls
        if (!urls) continue
        inflight++
        const img = new Image()
        img.crossOrigin = "anonymous"
        img.decoding = "async"
        const done = () => {
          inflight--
          pump()
        }
        img.onload = () => {
          photoCache.set(id, img)
          drawThumb(id)
          done()
        }
        img.onerror = done
        img.src = thumbUrl(urls)
      }
    }

    map.setMissingStyleImageResolver((id) => {
      const [kind, a, b, c] = id.split(":")
      if (kind === "rose") {
        if (made.size > 600) {
          // Keep memory bounded on very long sessions.
          for (const old of [...made].slice(0, 300)) {
            if (map.hasImage(old)) map.removeImage(old)
            made.delete(old)
          }
        }
        made.add(id)
        add(id, roseSprite(Number(a), b, c.split(",").map(Number)))
      } else if (kind === "thumb" || kind === "thumbsel") {
        const bid = Number(a)
        add(id, thumbSprite(thumbArgs(bid, kind === "thumbsel")))
        if (!photoCache.has(bid) && !queue.includes(bid)) {
          queue.push(bid)
          pump()
        }
      }
    })

    const reportView = () => {
      const bd = map.getBounds()
      const c = map.getCenter()
      cb.current.onView({
        bounds: [bd.getWest(), bd.getSouth(), bd.getEast(), bd.getNorth()],
        center: [c.lng, c.lat],
        zoom: map.getZoom(),
      })
    }

    map.on("load", () => {
      restyle(map)
      // Start the attribution collapsed behind its (i) button.
      map
        .getContainer()
        .querySelector(".maplibregl-ctrl-attrib")
        ?.classList.remove("maplibregl-compact-show")
      for (const k of ["known", "est", "sel"] as const) {
        map.addImage(`m-${k}`, dotSprite(k).data, { pixelRatio: 2 })
      }
      map.addSource("benches", {
        type: "geojson",
        data: dots(benchesRef.current, visibleRef.current),
        cluster: true,
        // A wide radius and an early max zoom keep the city view to a handful
        // of roses so the photographed benches lead.
        clusterRadius: 96,
        clusterMaxZoom: 14,
        clusterProperties: SECTOR_PROPS,
      })
      map.addSource("photos", {
        type: "geojson",
        data: photos(benchesRef.current, visibleRef.current),
      })
      map.addSource("sel", { type: "geojson", data: empty })
      map.addLayer({
        id: "roses",
        type: "symbol",
        source: "benches",
        filter: ["has", "point_count"],
        layout: {
          "icon-image": ROSE_IMAGE,
          "icon-allow-overlap": true,
          "icon-size": ["interpolate", ["linear"], ["zoom"], 10, 0.72, 14, 1],
        },
        paint: {
          "icon-opacity": [
            "interpolate",
            ["linear"],
            ["zoom"],
            11,
            0.85,
            14,
            1,
          ],
        },
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
      // Photographed benches: postcard sprites, decluttered by collision so the
      // sharpest-placed ones win at low zoom and the rest appear as you zoom in.
      map.addLayer({
        id: "thumbs",
        type: "symbol",
        source: "photos",
        layout: {
          "icon-image": ["concat", "thumb:", ["to-string", ["get", "id"]]],
          "icon-anchor": "bottom",
          "icon-allow-overlap": false,
          "icon-padding": 3,
          "symbol-sort-key": ["get", "id"],
        },
      })
      map.addLayer({
        id: "sel-dot",
        type: "symbol",
        source: "sel",
        filter: ["!", ["get", "photo"]],
        layout: {
          "icon-image": "m-sel",
          "icon-rotate": ["get", "facing"],
          "icon-rotation-alignment": "map",
          "icon-allow-overlap": true,
          "icon-size": 1.2,
        },
      })
      map.addLayer({
        id: "sel-thumb",
        type: "symbol",
        source: "sel",
        filter: ["get", "photo"],
        layout: {
          "icon-image": ["concat", "thumbsel:", ["to-string", ["get", "id"]]],
          "icon-anchor": "bottom",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      })

      const pick = (layer: string) => {
        map.on("click", layer, (e) => {
          const id = e.features?.[0]?.properties?.id
          if (typeof id === "number") cb.current.onSelect(id)
        })
      }
      pick("bench")
      pick("thumbs")
      pick("sel-thumb")
      map.on("click", "roses", (e) => {
        const f = e.features?.[0]
        if (!f) return
        map.easeTo({
          center: (f.geometry as unknown as { coordinates: [number, number] })
            .coordinates,
          zoom: map.getZoom() + 2,
        })
      })
      for (const layer of ["bench", "thumbs", "roses", "sel-thumb"]) {
        map.on("mouseenter", layer, () => {
          map.getCanvas().style.cursor = "pointer"
        })
        map.on("mouseleave", layer, () => {
          map.getCanvas().style.cursor = ""
        })
      }
      map.on("moveend", reportView)
      prefetch()
      reportView()
      setReady(true)
    })

    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  // Filters change which benches are on the map.
  useEffect(() => {
    if (!ready) return
    const map = mapRef.current
    ;(map?.getSource("benches") as GeoJSONSource | undefined)?.setData(
      dots(benches, visible)
    )
    ;(map?.getSource("photos") as GeoJSONSource | undefined)?.setData(
      photos(benches, visible)
    )
  }, [ready, benches, visible])

  // The one vermilion bench.
  useEffect(() => {
    if (!ready) return
    const src = mapRef.current?.getSource("sel") as GeoJSONSource | undefined
    const b = selectedId === null ? undefined : byId.get(selectedId)
    src?.setData(
      b
        ? {
            type: "FeatureCollection",
            features: [
              {
                type: "Feature",
                geometry: b.geometry,
                properties: {
                  id: b.properties.id,
                  facing: b.properties.facing ?? 0,
                  photo: hasPhoto(b),
                },
              },
            ],
          }
        : empty
    )
  }, [ready, byId, selectedId])

  // Back/forward: follow the URL when it names a different viewport.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !viewport) return
    const c = map.getCenter()
    if (!sameView(viewport, { lat: c.lat, lng: c.lng, z: map.getZoom() })) {
      map.jumpTo({ center: [viewport.lng, viewport.lat], zoom: viewport.z })
    }
  }, [ready, viewport])

  useEffect(() => {
    const map = mapRef.current
    if (flyTo && map) {
      map.flyTo({ center: flyTo.center, zoom: Math.max(map.getZoom(), 15) })
    }
  }, [flyTo])

  return (
    <div
      ref={container}
      className="map-canvas"
      role="application"
      aria-label="Map of benches. The postcards beside it list the same benches."
    />
  )
}
