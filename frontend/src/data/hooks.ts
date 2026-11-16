import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import { benchDetailQuery, benchesQuery, manifestQuery } from "./api"
import type { BenchFeature } from "./types"

export function useManifest() {
  return useQuery(manifestQuery)
}

export function useBenches() {
  const manifest = useManifest()
  const benches = useQuery(benchesQuery(manifest.data))
  return {
    data: benches.data,
    isPending: manifest.isPending || benches.isPending,
    error: manifest.error ?? benches.error,
  }
}

/** Benches at a place: 1 for old data without `count`. */
export const benchCount = (p: { count?: number }) => p.count ?? 1

/** Every bench id, including those that are not a place's leader, to its place. */
export function placeIndex(places: BenchFeature[]): Map<number, BenchFeature> {
  const index = new Map<number, BenchFeature>()
  for (const f of places) {
    for (const id of f.properties.bench_ids ?? [f.properties.id])
      index.set(id, f)
  }
  return index
}

export function useBenchIndex() {
  const { data } = useBenches()
  return useMemo(() => placeIndex(data ?? []), [data])
}

export function useBench(id: number) {
  const manifest = useManifest()
  const detail = useQuery(benchDetailQuery(manifest.data, id))
  return {
    data: detail.data,
    isPending: manifest.isPending || detail.isPending,
    error: manifest.error ?? detail.error,
  }
}
