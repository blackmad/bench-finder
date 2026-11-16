import "maplibre-gl/dist/maplibre-gl.css"
import { Map as MapLibreMap, setWorkerUrl } from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"
import { useEffect, useRef } from "react"
import { benchSprite } from "./sprites"
import { restyle, STYLE_URL } from "./style"

setWorkerUrl(workerUrl)

/** Where the bench is: one vermilion marker, needle only if the facing is known. */
export default function MiniMap({
  lat,
  lng,
  facing,
  label,
}: {
  lat: number
  lng: number
  facing: number | null
  label: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const map = new MapLibreMap({
      container: ref.current,
      style: STYLE_URL,
      center: [lng, lat],
      zoom: 16.4,
      attributionControl: { compact: true },
      dragRotate: false,
      maxPitch: 0,
      cooperativeGestures: true,
      locale: { "Map.Title": label },
    })
    map.touchZoomRotate.disableRotation()
    map.on("load", () => {
      restyle(map)
      map
        .getContainer()
        .querySelector(".maplibregl-ctrl-attrib")
        ?.classList.remove("maplibregl-compact-show")
      map.addImage("here", benchSprite("sel", facing !== null).data, {
        pixelRatio: 2,
      })
      map.addSource("here", {
        type: "geojson",
        data: {
          type: "Feature",
          geometry: { type: "Point", coordinates: [lng, lat] },
          properties: { f: facing ?? 0 },
        },
      })
      map.addLayer({
        id: "here",
        type: "symbol",
        source: "here",
        layout: {
          "icon-image": "here",
          "icon-rotate": ["get", "f"],
          "icon-rotation-alignment": "map",
          "icon-allow-overlap": true,
          "icon-size": 1.4,
        },
      })
    })
    return () => map.remove()
  }, [lat, lng, facing, label])
  return <div ref={ref} className="map-canvas" />
}
