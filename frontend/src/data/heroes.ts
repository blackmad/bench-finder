import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, unwrap } from "../lib/api"
import type { BenchProps, GalleryImage, ImageUrls } from "./types"

/** A lead photo a moderator chose on the site (before a publish bakes it in). */
export interface HeroPick {
  imageId: number
  key: string
  urls: ImageUrls
  urls_webp?: ImageUrls
  width: number
  height: number
}

export interface HeroSuggestion {
  id: number
  benchId: number
  imageId: number
  key: string
  photo: Omit<HeroPick, "imageId" | "key">
  current: Omit<HeroPick, "imageId" | "key"> | null
  who: string
  createdAt: string
}

const PICKS = ["heroes"]

export function useHeroPicks() {
  return useQuery({
    queryKey: PICKS,
    queryFn: async () =>
      unwrap<{ picks: Record<string, HeroPick> }>(await api.api.heroes.$get()),
    staleTime: 60_000,
    select: (d) => d.picks,
  })
}

/** The bench with a moderator's pick as its lead photo, if there is one. */
export function applyPick<P extends Partial<BenchProps>>(
  p: P,
  pick: HeroPick | undefined
): P {
  if (!pick || p.hero_key === pick.key) return p
  return {
    ...p,
    hero_key: pick.key,
    hero_urls: pick.urls,
    hero_urls_webp: pick.urls_webp ?? null,
    hero_width: pick.width,
    hero_height: pick.height,
    // The automatic crop's focus was for the old photo.
    hero_focus: null,
  }
}

/** What the worker needs to show a gallery photo as the lead. */
export const pickBody = (g: GalleryImage & { id: number }) => ({
  imageId: g.id,
  photo: {
    urls: g.urls,
    ...(g.urls_webp ? { urls_webp: g.urls_webp } : {}),
    width: g.width,
    height: g.height,
  },
})

export function useSetHero(benchId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (g: GalleryImage & { id: number }) =>
      unwrap(
        await api.api.admin.bench[":id"].hero.$put({
          param: { id: String(benchId) },
          json: pickBody(g),
        })
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: PICKS }),
  })
}

export function useClearHero(benchId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.api.admin.bench[":id"].hero.$delete({
          param: { id: String(benchId) },
        })
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: PICKS }),
  })
}

export function useSuggestHero(benchId: number) {
  return useMutation({
    mutationFn: async (g: GalleryImage & { id: number }) =>
      unwrap(
        await api.api.bench[":id"]["hero-suggestions"].$post({
          param: { id: String(benchId) },
          json: pickBody(g),
        })
      ),
  })
}

export function useHeroSuggestions() {
  return useQuery({
    queryKey: ["admin", "hero-suggestions"],
    queryFn: async () =>
      unwrap<{ suggestions: HeroSuggestion[] }>(
        await api.api.admin["hero-suggestions"].$get()
      ),
  })
}

export function useResolveSuggestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; action: "accept" | "dismiss" }) =>
      unwrap(
        await api.api.admin["hero-suggestions"][":id"][":action"].$post({
          param: { id: String(v.id), action: v.action },
        })
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin"] })
      qc.invalidateQueries({ queryKey: PICKS })
    },
  })
}

export function useSuggestView(benchId: number) {
  return useMutation({
    mutationFn: async (json: {
      panoId: string
      heading: number
      pitch: number
      fov: number
    }) =>
      unwrap(
        await api.api.bench[":id"]["view-suggestions"].$post({
          param: { id: String(benchId) },
          json,
        })
      ),
  })
}

export interface ViewSuggestion {
  id: number
  benchId: number
  panoId: string
  heading: number
  pitch: number
  fov: number
  who: string
  state: "pending" | "rendered" | "failed"
  imageId: number | null
  error: string | null
  createdAt: string
}

export function useViewSuggestions() {
  return useQuery({
    queryKey: ["admin", "view-suggestions"],
    queryFn: async () =>
      unwrap<{ views: ViewSuggestion[] }>(
        await api.api.admin["view-suggestions"].$get()
      ),
  })
}

export function useDismissView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.api.admin["view-suggestions"][":id"].dismiss.$post({
          param: { id: String(id) },
        })
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  })
}
