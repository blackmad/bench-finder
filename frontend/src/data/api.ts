import { queryOptions } from "@tanstack/react-query"
import type {
  BenchCollection,
  BenchDetail,
  BenchFeature,
  ImageUrls,
  Manifest,
} from "./types"

const BASE = (import.meta.env.VITE_DATA_BASE_URL ?? "/data").replace(/\/$/, "")

/** Resolve a path from the data files against the data base URL. */
export function dataUrl(path: string): string {
  return /^https?:\/\//.test(path) ? path : `${BASE}/${path.replace(/^\//, "")}`
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(dataUrl(path))
  if (!res.ok) throw new Error(`Could not load ${path} (${res.status})`)
  return (await res.json()) as T
}

// The manifest is the only un-hashed file, so it is always revalidated; the
// hashed files it points to are immutable and can be cached forever.
export const manifestQuery = queryOptions({
  queryKey: ["manifest"],
  queryFn: () => getJson<Manifest>("manifest.json"),
  staleTime: 5 * 60_000,
})

/** Path of a data file named in the manifest, honouring `data_base`. */
function manifestPath(m: Manifest, ...parts: string[]): string {
  return [m.data_base, ...parts]
    .filter((x): x is string => Boolean(x))
    .map((x) => x.replace(/^\/+|\/+$/g, ""))
    .join("/")
}

export const benchesQuery = (manifest: Manifest | undefined) =>
  queryOptions({
    queryKey: ["benches", manifest?.benches],
    queryFn: async () => {
      const fc = await getJson<BenchCollection>(
        manifest ? manifestPath(manifest, manifest.benches) : ""
      )
      return fc.features
    },
    enabled: Boolean(manifest),
    staleTime: Number.POSITIVE_INFINITY,
  })

export const benchDetailQuery = (manifest: Manifest | undefined, id: number) =>
  queryOptions({
    queryKey: ["bench", manifest?.generated_at, id],
    queryFn: () =>
      getJson<BenchDetail>(
        manifest ? manifestPath(manifest, manifest.bench_dir, `${id}.json`) : ""
      ),
    enabled: Boolean(manifest) && Number.isFinite(id),
    staleTime: Number.POSITIVE_INFINITY,
  })

/** Build a srcset string from width-keyed renditions. */
export function srcSet(urls: ImageUrls | null): string | undefined {
  if (!urls) return undefined
  const entries = Object.entries(urls)
  if (entries.length < 2) return undefined
  return entries
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([w, u]) => `${dataUrl(u)} ${w}w`)
    .join(", ")
}

/** The widest rendition, used as the plain `src`. */
export function bestUrl(urls: ImageUrls | null): string | undefined {
  if (!urls) return undefined
  const widest = Object.keys(urls).sort((a, b) => Number(b) - Number(a))[0]
  return widest ? dataUrl(urls[widest]) : undefined
}

export const hasPhoto = (f: BenchFeature): boolean =>
  Boolean(f.properties.hero_urls)
