import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, unwrap } from "../lib/api"
import { useAuth } from "../lib/auth"
import { withUsername } from "../lib/username"

export interface Comment {
  id: number
  displayName: string
  body: string
  createdAt: string
  mine: boolean
  /** Stars the author gave with the note. */
  rating?: number | null
}
export interface Social {
  benchId: number
  ratings: { count: number; average: number | null }
  comments: Comment[]
  me: {
    rating: number | null
    visited: boolean
    favorite: boolean
    want: boolean
  } | null
}
export interface Me {
  uid: string
  isAdmin: boolean
  ratings: { benchId: number; rating: number }[]
  visited: number[]
  favorites: number[]
  want: number[]
  profile: Profile | null
}
export interface Profile {
  slug: string
  handle: string | null
  displayName: string
  public: boolean
}
export interface PublicPage {
  displayName: string
  handle: string | null
  slug: string
  favorites: number[]
}
export type FeedItem =
  | {
      kind: "note"
      key: string
      benchId: number
      at: string
      who: string
      text: string
      rating: number | null
    }
  | {
      kind: "rating"
      key: string
      benchId: number
      at: string
      rating: number
      who?: string | null
    }
  | {
      kind: "fave"
      key: string
      benchId: number
      at: string
      who: string
      page: string
    }

/** The public page's path: the handle once chosen, else the share slug. */
export const pagePath = (p: Pick<Profile, "slug" | "handle">) =>
  `/u/${p.handle ?? p.slug}`

/** Moves `ids[i]` by `d` places (a no-op at the ends). */
export function moved(ids: number[], i: number, d: -1 | 1): number[] {
  const j = i + d
  if (i < 0 || j < 0 || j >= ids.length) return ids
  const out = [...ids]
  ;[out[i], out[j]] = [out[j], out[i]]
  return out
}

export function useSocial(benchId: number) {
  const { user } = useAuth()
  return useQuery({
    queryKey: ["social", benchId, user?.uid ?? null],
    queryFn: async () =>
      unwrap<Social>(
        await api.api.bench[":id"].social.$get({
          param: { id: String(benchId) },
        })
      ),
  })
}

export function useMe() {
  const { user } = useAuth()
  return useQuery({
    queryKey: ["me", user?.uid ?? null],
    queryFn: async () => unwrap<Me>(await api.api.me.$get()),
    enabled: Boolean(user),
  })
}

/** Run an optimistic edit on the cached social payload, rolling back on error. */
function useSocialMutation<V>(
  benchId: number,
  mutationFn: (v: V) => Promise<unknown>,
  patch: (s: Social, v: V) => Social
) {
  const qc = useQueryClient()
  const { user } = useAuth()
  const key = ["social", benchId, user?.uid ?? null]
  return useMutation({
    mutationFn,
    onMutate: async (v: V) => {
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<Social>(key)
      if (prev) qc.setQueryData<Social>(key, patch(prev, v))
      return { prev }
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["social", benchId] })
      qc.invalidateQueries({ queryKey: ["me"] })
    },
  })
}

export function useRate(benchId: number) {
  // null clears your rating.
  return useSocialMutation<number | null>(
    benchId,
    async (rating) =>
      unwrap(
        rating === null
          ? await api.api.bench[":id"].rating.$delete({
              param: { id: String(benchId) },
            })
          : await api.api.bench[":id"].rating.$put({
              param: { id: String(benchId) },
              json: { rating },
            })
      ),
    (s, rating) => {
      const old = s.me?.rating ?? null
      const count =
        s.ratings.count + (old === null ? 1 : 0) - (rating === null ? 1 : 0)
      const sum =
        (s.ratings.average ?? 0) * s.ratings.count - (old ?? 0) + (rating ?? 0)
      return {
        ...s,
        ratings: {
          count,
          average: count ? Math.round((sum / count) * 100) / 100 : null,
        },
        me: { visited: false, favorite: false, want: false, ...s.me, rating },
      }
    }
  )
}

export function useSetStatus(benchId: number) {
  return useSocialMutation<{
    visited?: boolean
    favorite?: boolean
    want?: boolean
  }>(
    benchId,
    async (json) =>
      unwrap(
        await api.api.bench[":id"].status.$put({
          param: { id: String(benchId) },
          json,
        })
      ),
    (s, v) => ({
      ...s,
      me: {
        rating: null,
        visited: false,
        favorite: false,
        want: false,
        ...s.me,
        ...v,
      },
    })
  )
}

export function useAddComment(benchId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { body: string; rating?: number }) =>
      withUsername(async () =>
        unwrap<Comment>(
          await api.api.bench[":id"].comments.$post({
            param: { id: String(benchId) },
            json: v,
          })
        )
      ),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["social", benchId] })
      qc.invalidateQueries({ queryKey: ["me"] })
      qc.invalidateQueries({ queryKey: ["feed"] })
    },
  })
}

export function useDeleteComment(benchId: number) {
  return useSocialMutation<number>(
    benchId,
    async (id) =>
      unwrap(
        await api.api.comments[":id"].$delete({ param: { id: String(id) } })
      ),
    (s, id) => ({ ...s, comments: s.comments.filter((c) => c.id !== id) })
  )
}

export function useFlagComment() {
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.api.comments[":id"].flag.$post({
          param: { id: String(id) },
        })
      ),
  })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (
      json: Partial<Pick<Profile, "public" | "displayName">> & {
        handle?: string | null
      }
    ) => unwrap<Profile>(await api.api.me.profile.$put({ json })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  })
}

/** Saves the favourites' order; the cached list updates at once. */
export function useReorderFavorites() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const key = ["me", user?.uid ?? null]
  return useMutation({
    mutationFn: async (ids: number[]) =>
      unwrap(await api.api.me.favorites.order.$put({ json: { ids } })),
    onMutate: async (ids: number[]) => {
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<Me>(key)
      if (prev) qc.setQueryData<Me>(key, { ...prev, favorites: ids })
      return { prev }
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev)
    },
  })
}

export function usePublicPage(key: string) {
  return useQuery({
    queryKey: ["u", key.toLowerCase()],
    queryFn: async () =>
      unwrap<PublicPage>(await api.api.u[":key"].$get({ param: { key } })),
    retry: false,
  })
}

export function useFeed() {
  return useQuery({
    queryKey: ["feed"],
    queryFn: async () =>
      unwrap<{ items: FeedItem[] }>(
        await api.api.feed.$get({ query: { limit: "20" } })
      ),
    staleTime: 60_000,
  })
}
