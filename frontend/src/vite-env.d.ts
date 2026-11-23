/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the published static data (manifest.json, GeoJSON, images). */
  readonly VITE_DATA_BASE_URL?: string
  readonly VITE_SENTRY_RELEASE?: string
  /** Base URL of the Worker that handles user writes. Empty = same origin. */
  readonly VITE_API_BASE_URL?: string
  readonly VITE_FIREBASE_API_KEY?: string
  readonly VITE_FIREBASE_AUTH_DOMAIN?: string
  readonly VITE_FIREBASE_PROJECT_ID?: string
  /** Cloudflare Turnstile site key for anonymous reports. */
  readonly VITE_TURNSTILE_SITE_KEY?: string
  /** Maps Embed API key (free, referrer-restricted) for the bench Street View. */
  readonly VITE_GOOGLE_MAPS_EMBED_KEY?: string
  /** Optional key with the Maps JavaScript API (Find a better view); else the embed key. */
  readonly VITE_GOOGLE_MAPS_JS_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
