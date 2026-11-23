import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import {
  api,
  benchPhotoSrc,
  postBenchPhoto,
  privatePhotoUrl,
  unwrap,
} from "../lib/api"
import { useAuth } from "../lib/auth"
import { withUsername } from "../lib/username"
import { compressImage } from "../utils/imageCapture"

export interface BenchPhoto {
  id: number
  path: string
  width: number
  height: number
  who: string
  state: "pending" | "visible" | "hidden"
  createdAt: string
  mine: boolean
  benchId?: number
}

export function useBenchPhotos(benchId: number) {
  const { user } = useAuth()
  return useQuery({
    queryKey: ["photos", benchId, user?.uid ?? null],
    queryFn: async () =>
      unwrap<{ photos: BenchPhoto[] }>(
        await api.api.bench[":id"].photos.$get({
          param: { id: String(benchId) },
        })
      ),
  })
}

/** Downsizes to 2048 px JPEG in the browser (which also drops GPS metadata), then uploads. */
export function useUploadPhoto(benchId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const img = await compressImage(file, 2048, 2048, 0.85)
      return withUsername(() =>
        postBenchPhoto(benchId, img.blob, img.width, img.height)
      )
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["photos", benchId] }),
  })
}

export function useDeletePhoto(benchId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.api["bench-photos"][":id"].$delete({
          param: { id: String(id) },
        })
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: ["photos", benchId] }),
  })
}

export function usePendingPhotos(enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "photos"],
    queryFn: async () =>
      unwrap<{ photos: BenchPhoto[] }>(
        await api.api.admin["bench-photos"].$get()
      ),
    enabled,
  })
}

export function useModeratePhoto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; action: "approve" | "hide" }) =>
      unwrap(
        await api.api.admin["bench-photos"][":id"][":action"].$post({
          param: { id: String(v.id), action: v.action },
        })
      ),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["admin", "photos"] })
      qc.invalidateQueries({ queryKey: ["photos"] })
    },
  })
}

/** An <img> src for a photo: direct when public, else fetched with the token. */
export function usePhotoSrc(p: BenchPhoto): string | null {
  const [blob, setBlob] = useState<string | null>(null)
  const isPublic = p.state === "visible"
  useEffect(() => {
    if (isPublic) return
    let url: string | null = null
    let live = true
    privatePhotoUrl(p.path)
      .then((u) => {
        url = u
        if (live) setBlob(u)
        else URL.revokeObjectURL(u)
      })
      .catch(() => {})
    return () => {
      live = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [p.path, isPublic])
  return isPublic ? benchPhotoSrc(p.path) : blob
}
