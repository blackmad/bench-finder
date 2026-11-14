import "maplibre-gl/dist/maplibre-gl.css"
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"
import { useEffect, useRef } from "react"

setWorkerUrl(workerUrl)

export interface Point {
  lat: number
  lng: number
}

/** Small map: click or drag the pin to choose where the missing bench is. */
export default function MapPicker({
  point,
  onChange,
}: {
  point: Point
  onChange: (p: Point) => void
}) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markerRef = useRef<Marker | null>(null)
  const cb = useRef(onChange)
  cb.current = onChange
  const initial = useRef(point)

  useEffect(() => {
    if (!container.current) return
    const map = new MapLibreMap({
      container: container.current,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: [initial.current.lng, initial.current.lat],
      zoom: 17,
      attributionControl: { compact: true },
      dragRotate: false,
      locale: {
        "Map.Title":
          "Map: click or drag the pin to where the bench is. With the keyboard, arrow keys move the map and the pin moves to its centre.",
      },
    })
    map.addControl(new NavigationControl({ showCompass: false }), "top-right")
    const marker = new Marker({ color: "#e23b1e", draggable: true })
      .setLngLat([initial.current.lng, initial.current.lat])
      .addTo(map)
    marker.on("dragend", () => {
      const p = marker.getLngLat()
      cb.current({ lat: p.lat, lng: p.lng })
    })
    // Keyboard path: after an arrow-key pan the pin follows the map centre.
    map.on("moveend", (e) => {
      if (!(e.originalEvent instanceof KeyboardEvent)) return
      const c = map.getCenter()
      marker.setLngLat(c)
      cb.current({ lat: c.lat, lng: c.lng })
    })
    map.on("click", (e) => {
      marker.setLngLat(e.lngLat)
      cb.current({ lat: e.lngLat.lat, lng: e.lngLat.lng })
    })
    mapRef.current = map
    markerRef.current = marker
    return () => {
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
  }, [])

  // Follow external changes (use my location).
  useEffect(() => {
    markerRef.current?.setLngLat([point.lng, point.lat])
    mapRef.current?.easeTo({ center: [point.lng, point.lat], duration: 250 })
  }, [point.lat, point.lng])

  return <div ref={container} className="pickmap" />
}
