import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import { benchDetailQuery, benchesQuery, manifestQuery } from "./api"
import { applyPick, useHeroPicks } from "./heroes"
import type { BenchFeature } from "./types"

export function useManifest() {
  return useQuery(manifestQuery)
}

export function useBenches() {
  const manifest = useManifest()
  const benches = useQuery(benchesQuery(manifest.data))
  // Moderators' lead photo picks show at once, before the next publish.
  const { data: picks } = useHeroPicks()
  const data = useMemo(
    () =>
      picks && benches.data
        ? benches.data.map((f) => {
            const pick = picks[f.properties.id]
            return pick
              ? { ...f, properties: applyPick(f.properties, pick) }
              : f
          })
        : benches.data,
    [benches.data, picks]
  )
  return {
    data,
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
  const { data: picks } = useHeroPicks()
  const pick = picks?.[id]
  const data = useMemo(
    () => (detail.data ? applyPick(detail.data, pick) : detail.data),
    [detail.data, pick]
  )
  return {
    data,
    isPending: manifest.isPending || detail.isPending,
    error: manifest.error ?? detail.error,
  }
}
