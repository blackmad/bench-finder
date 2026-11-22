import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, unwrap } from "../lib/api"
import { useAuth } from "../lib/auth"

export interface Comment {
  id: number
  displayName: string
  body: string
  createdAt: string
  mine: boolean
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
  return useSocialMutation<number>(
    benchId,
    async (rating) =>
      unwrap(
        await api.api.bench[":id"].rating.$put({
          param: { id: String(benchId) },
          json: { rating },
        })
      ),
    (s, rating) => {
      const old = s.me?.rating ?? null
      const count = s.ratings.count + (old === null ? 1 : 0)
      const sum =
        (s.ratings.average ?? 0) * s.ratings.count - (old ?? 0) + rating
      return {
        ...s,
        ratings: { count, average: Math.round((sum / count) * 100) / 100 },
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
    mutationFn: async (body: string) =>
      unwrap<Comment>(
        await api.api.bench[":id"].comments.$post({
          param: { id: String(benchId) },
          json: { body },
        })
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: ["social", benchId] }),
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
