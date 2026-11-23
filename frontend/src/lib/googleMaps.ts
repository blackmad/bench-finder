/** Loads the Google Maps JavaScript API once, on demand (it is billed per load). */

// Just the Street View surface we use; avoids a dependency on @types/google.maps.
export interface StreetViewPov {
  heading: number
  pitch: number
}
export interface StreetViewPanorama {
  getPano(): string
  getPov(): StreetViewPov
  getZoom(): number
  getPosition(): { lat(): number; lng(): number } | null
  addListener(event: string, fn: () => void): { remove(): void }
}
interface MapsNamespace {
  StreetViewPanorama: new (
    el: HTMLElement,
    opts: Record<string, unknown>
  ) => StreetViewPanorama
}

const KEY =
  import.meta.env.VITE_GOOGLE_MAPS_JS_KEY ??
  import.meta.env.VITE_GOOGLE_MAPS_EMBED_KEY

let loading: Promise<MapsNamespace> | null = null

export function loadGoogleMaps(): Promise<MapsNamespace> {
  if (!KEY) return Promise.reject(new Error("No Google Maps key configured"))
  if (loading) return loading
  loading = new Promise<MapsNamespace>((resolve, reject) => {
    const w = window as unknown as Record<string, unknown>
    const cb = "__bfGoogleMapsReady"
    w[cb] = () =>
      resolve((w.google as { maps: MapsNamespace }).maps as MapsNamespace)
    // Google reports a bad or restricted key here, not as a load error.
    w.gm_authFailure = () =>
      reject(new Error("Google rejected the Maps key for this site"))
    const s = document.createElement("script")
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(KEY)}&v=weekly&loading=async&callback=${cb}`
    s.async = true
    s.onerror = () => reject(new Error("Could not load Google Maps"))
    document.head.append(s)
  }).catch((e) => {
    loading = null
    throw e
  })
  return loading
}

/** Street View's zoom to a horizontal field of view in degrees (zoom 1 = 90). */
export const zoomToFov = (zoom: number) =>
  Math.min(120, Math.max(10, 180 / 2 ** zoom))
