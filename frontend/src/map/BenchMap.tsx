import "maplibre-gl/dist/maplibre-gl.css"
import {
  type ExpressionSpecification,
  type GeoJSONSource,
  Map as MapLibreMap,
  NavigationControl,
  type SymbolLayerSpecification,
  setWorkerUrl,
} from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"
import { useEffect, useMemo, useRef, useState } from "react"
import { dataUrl, hasPhoto } from "../data/api"
import { isKnown, sectorOf } from "../data/facing"
import type { BenchFeature, ImageUrls } from "../data/types"
import type { Viewport } from "../lib/viewport"
import { dotSprite, roseSprite, type Sprite, thumbSprite } from "./sprites"
import { type MapView, restyle, STYLE_URL } from "./style"

// maplibre-gl 6 locates its worker next to its own module; once bundled that
// path no longer exists, so point it at the bundled worker explicitly.
setWorkerUrl(workerUrl)

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
// Numbers on the map count separate places (what a marker would split into),
// not benches: a place of four benches is one marker with no badge.
const SECTOR_PROPS = Object.fromEntries(
  [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [`s${i}`, sectorExpr(i)])
)
const N_ABBR: ExpressionSpecification = [
  "case",
  [">=", ["get", "point_count"], 1000],
  [
    "concat",
    ["to-string", ["/", ["round", ["/", ["get", "point_count"], 100]], 10]],
    "k",
  ],
  ["to-string", ["get", "point_count"]],
]

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
  N_ABBR,
  ":",
  ...[0, 1, 2, 3, 4, 5, 6, 7].flatMap((i) => [levelExpr(i), i < 7 ? "," : ""]),
]

// Below this zoom the map shows counts and compass dots only; the rail beside
// it carries the photos. From here on, photographed benches are postcards.
const PHOTO_ZOOM = 16

const empty = { type: "FeatureCollection" as const, features: [] }

// The selected bench is drawn by its own "sel" layer, so it is left out of the
// clustered sources: otherwise it shows twice (alone and inside a cluster count).
const shown = (
  b: BenchFeature,
  visible: ReadonlySet<number>,
  selected: number | null
) => visible.has(b.properties.id) && b.properties.id !== selected

function dots(
  benches: BenchFeature[],
  visible: ReadonlySet<number>,
  selected: number | null = null
) {
  return {
    type: "FeatureCollection" as const,
    features: benches
      // Every bench: photographed ones are dots too until PHOTO_ZOOM, where
      // the "bench" layer leaves them to the postcard layer.
      .filter((b) => shown(b, visible, selected))
      .map((b) => ({
        type: "Feature" as const,
        geometry: b.geometry,
        properties: {
          id: b.properties.id,
          n: b.properties.count ?? 1,
          photo: hasPhoto(b),
          facing: b.properties.facing ?? 0,
          // Benches without a facing count toward no sector (-1), so a
          // cluster rose only grows ticks for facings the data really has.
          sec:
            b.properties.facing === null ? -1 : sectorOf(b.properties.facing),
          kind:
            b.properties.facing === null
              ? "none"
              : isKnown(b.properties)
                ? "known"
                : "est",
        },
      })),
  }
}

function photos(
  benches: BenchFeature[],
  visible: ReadonlySet<number>,
  selected: number | null = null
) {
  return {
    type: "FeatureCollection" as const,
    features: benches
      .filter((b) => hasPhoto(b) && shown(b, visible, selected))
      .map((b) => ({
        type: "Feature" as const,
        geometry: b.geometry,
        properties: { id: b.properties.id, n: b.properties.count ?? 1 },
      })),
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
  const selectedRef = useRef(selectedId)
  selectedRef.current = selectedId
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
      // The canvas is the focusable element (arrow keys pan, +/- zoom).
      locale: {
        "Map.Title":
          "Map of benches. Arrow keys pan, plus and minus zoom. Photographed benches in view are also listed after the map.",
      },
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
    // Count-badged sprites drawn for each representative bench, so its photo
    // can be painted into them once it arrives.
    const groupSprites = new Map<number, Set<number>>()
    const thumbArgs = (id: number, selected: boolean, count = 1) => ({
      photo: photoCache.get(id) ?? null,
      selected,
      count,
    })
    const drawThumb = (id: number) => {
      add(`thumb:${id}`, thumbSprite(thumbArgs(id, false)))
      const sel = `thumbsel:${id}`
      if (map.hasImage(sel)) add(sel, thumbSprite(thumbArgs(id, true)))
      for (const n of groupSprites.get(id) ?? []) {
        add(`thumbc:${id}:${n}`, thumbSprite(thumbArgs(id, false, n)))
      }
      // updateImage alone does not repaint an idle map.
      map.triggerRepaint()
    }
    // A collapsed photo marker shows its lowest-id member's photo.
    const photoId = (props: Record<string, unknown> | null | undefined) =>
      Number(props?.cluster ? props.rep : props?.id)
    // Fetch photos only for thumbnails MapLibre actually placed. The missing-
    // image resolver fires for every feature in a tile before collision, so
    // queueing there would fetch every photographed bench in the city at once.
    const fetchPlaced = () => {
      if (!map.getLayer("thumbs")) return
      const placed = map.queryRenderedFeatures({
        layers: ["thumbs", "sel-thumb"],
      })
      for (const f of placed) {
        const id = photoId(f.properties)
        if (!photoCache.has(id) && !queue.includes(id)) queue.push(id)
      }
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
      } else if (kind === "thumbc") {
        const bid = Number(a)
        const n = Number(b)
        if (!groupSprites.has(bid)) groupSprites.set(bid, new Set())
        groupSprites.get(bid)?.add(n)
        add(id, thumbSprite(thumbArgs(bid, false, n)))
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
      map.addImage("m-none", dotSprite("known", false).data, { pixelRatio: 2 })
      map.addImage("m-selnone", dotSprite("sel", false).data, {
        pixelRatio: 2,
      })
      map.addSource("benches", {
        type: "geojson",
        data: dots(benchesRef.current, visibleRef.current, selectedRef.current),
        cluster: true,
        // A wide radius and an early max zoom keep the city view to a handful
        // of roses so the photographed benches lead.
        clusterRadius: 96,
        clusterMaxZoom: 14,
        clusterProperties: SECTOR_PROPS,
      })
      // Photographed benches cluster like the dots do, never by silent
      // collision: a collapsed marker carries the count of benches it holds.
      map.addSource("photos", {
        type: "geojson",
        data: photos(
          benchesRef.current,
          visibleRef.current,
          selectedRef.current
        ),
        cluster: true,
        clusterRadius: 52,
        clusterMaxZoom: 19,
        clusterProperties: { rep: ["min", ["get", "id"]] },
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
      const dotLayout: SymbolLayerSpecification["layout"] = {
        "icon-image": ["concat", "m-", ["get", "kind"]],
        "icon-rotate": ["get", "facing"],
        "icon-rotation-alignment": "map",
        "icon-allow-overlap": true,
        "icon-size": 0.86,
      }
      map.addLayer({
        id: "bench",
        type: "symbol",
        source: "benches",
        filter: ["all", ["!", ["has", "point_count"]], ["!", ["get", "photo"]]],
        layout: dotLayout,
      })
      // Photographed benches are plain dots until the map shows a few streets.
      map.addLayer({
        id: "bench-photo",
        type: "symbol",
        source: "benches",
        maxzoom: PHOTO_ZOOM,
        filter: ["all", ["!", ["has", "point_count"]], ["get", "photo"]],
        layout: dotLayout,
      })
      // Photographed benches: postcard sprites. A cluster shows one member's
      // photo with a count badge; every bench is on the map in some marker.
      map.addLayer({
        id: "thumbs",
        type: "symbol",
        source: "photos",
        minzoom: PHOTO_ZOOM,
        layout: {
          "icon-image": [
            "case",
            ["has", "point_count"],
            [
              "concat",
              "thumbc:",
              ["to-string", ["get", "rep"]],
              ":",
              ["to-string", ["get", "point_count"]],
            ],
            ["concat", "thumb:", ["to-string", ["get", "id"]]],
          ],
          "icon-anchor": "bottom",
          "icon-allow-overlap": true,
          "symbol-sort-key": ["-", 0, ["coalesce", ["get", "point_count"], 1]],
        },
      })
      map.addLayer({
        id: "sel-dot",
        type: "symbol",
        source: "sel",
        filter: ["!", ["get", "photo"]],
        layout: {
          "icon-image": ["case", ["get", "faced"], "m-sel", "m-selnone"],
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
      pick("bench-photo")
      pick("sel-thumb")
      map.on("click", "thumbs", async (e) => {
        const f = e.features?.[0]
        if (!f) return
        const p = f.properties ?? {}
        if (!p.cluster) {
          if (typeof p.id === "number") cb.current.onSelect(p.id)
          return
        }
        // A collapsed marker opens up to the zoom where its benches separate.
        const src = map.getSource("photos") as GeoJSONSource
        const zoom = await src.getClusterExpansionZoom(Number(p.cluster_id))
        map.easeTo({
          center: (f.geometry as unknown as { coordinates: [number, number] })
            .coordinates,
          zoom: Math.min(zoom + 0.2, 20),
        })
      })
      map.on("click", "roses", (e) => {
        const f = e.features?.[0]
        if (!f) return
        map.easeTo({
          center: (f.geometry as unknown as { coordinates: [number, number] })
            .coordinates,
          zoom: map.getZoom() + 2,
        })
      })
      for (const layer of [
        "bench",
        "bench-photo",
        "thumbs",
        "roses",
        "sel-thumb",
      ]) {
        map.on("mouseenter", layer, () => {
          map.getCanvas().style.cursor = "pointer"
        })
        map.on("mouseleave", layer, () => {
          map.getCanvas().style.cursor = ""
        })
      }
      map.on("moveend", reportView)
      map.on("idle", fetchPlaced)
      reportView()
      setReady(true)
    })

    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  // Filters (and the selection, drawn on its own layer) change which benches
  // the clustered sources hold.
  useEffect(() => {
    if (!ready) return
    const map = mapRef.current
    ;(map?.getSource("benches") as GeoJSONSource | undefined)?.setData(
      dots(benches, visible, selectedId)
    )
    ;(map?.getSource("photos") as GeoJSONSource | undefined)?.setData(
      photos(benches, visible, selectedId)
    )
  }, [ready, benches, visible, selectedId])

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
                  faced: b.properties.facing !== null,
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

  return <div ref={container} className="map-canvas" />
}
