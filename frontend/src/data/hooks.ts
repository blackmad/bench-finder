import { useQuery } from "@tanstack/react-query"
import { benchDetailQuery, benchesQuery, manifestQuery } from "./api"

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

export function useBench(id: number) {
  const manifest = useManifest()
  const detail = useQuery(benchDetailQuery(manifest.data, id))
  return {
    data: detail.data,
    isPending: manifest.isPending || detail.isPending,
    error: manifest.error ?? detail.error,
  }
}
