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

/** The basemap re-inked as warm card stock: canal-blue water, parks a faint olive wash. */
export function restyle(map: MapLibreMap) {
  for (const l of map.getStyle().layers) {
    if (l.type === "background") {
      map.setPaintProperty(l.id, "background-color", "#f7f0e1")
    }
    if (/water/.test(l.id) && l.type === "fill") {
      map.setPaintProperty(l.id, "fill-color", "#a7cfe4")
    }
    // Residential and other built-up landuse melts into the paper; only real
    // green (parks, grass, woods) is green, so the city reads in two tones.
    if (/landuse|landcover/.test(l.id) && l.type === "fill") {
      map.setPaintProperty(l.id, "fill-color", "#f7f0e1")
    }
    if (
      /park|wood|grass|forest|garden|cemetery|pitch/.test(l.id) &&
      l.type === "fill"
    ) {
      map.setPaintProperty(l.id, "fill-color", "#e4e3c9")
    }
    if (/building/.test(l.id) && l.type === "fill") {
      map.setPaintProperty(l.id, "fill-color", "#ece4d4")
    }
    if (l.type === "symbol" && l.layout?.["text-field"]) {
      map.setPaintProperty(l.id, "text-color", "#5e5547")
    }
  }
}
