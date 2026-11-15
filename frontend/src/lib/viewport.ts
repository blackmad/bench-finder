export interface Viewport {
  lat: number
  lng: number
  z: number
}

export function viewportFromParams(sp: URLSearchParams): Viewport | null {
  const lat = Number.parseFloat(sp.get("lat") ?? "")
  const lng = Number.parseFloat(sp.get("lng") ?? "")
  const z = Number.parseFloat(sp.get("z") ?? "")
  if (![lat, lng, z].every(Number.isFinite)) return null
  if (Math.abs(lat) > 85 || Math.abs(lng) > 180 || z < 0 || z > 22) return null
  return { lat, lng, z }
}

export function viewportToParams(v: Viewport, sp: URLSearchParams) {
  sp.set("lat", v.lat.toFixed(5))
  sp.set("lng", v.lng.toFixed(5))
  sp.set("z", v.z.toFixed(2))
}
