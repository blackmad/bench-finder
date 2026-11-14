import type { Map as MapLibreMap } from "maplibre-gl"
import type { Viewport } from "../lib/viewport"

// Kept apart from the map components so pages can import these without
// pulling MapLibre into their own chunk.
export const STYLE_URL = "https://tiles.openfreemap.org/styles/positron"
export const START_VIEW: Viewport = { lat: 52.3715, lng: 4.893, z: 12.6 }

export interface MapView {
  bounds: [number, number, number, number]
  center: [number, number]
  zoom: number
}

/** The basemap re-inked as card stock, with airmail water. */
export function restyle(map: MapLibreMap) {
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
