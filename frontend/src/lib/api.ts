import { hc } from "hono/client"
import type { AppType } from "./worker-types"

const BASE = import.meta.env.VITE_API_BASE_URL ?? ""

type TokenProvider = () => Promise<string | null>
let tokenProvider: TokenProvider = async () => null

/** The auth provider registers how to get a fresh ID token (null when signed out). */
export function setTokenProvider(fn: TokenProvider) {
  tokenProvider = fn
}

/** Typed client for the Worker's /api routes. Attaches the ID token when signed in. */
export const api = hc<AppType>(BASE, {
  fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
    const token = await tokenProvider()
    const headers = new Headers(init?.headers)
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`)
    }
    return fetch(input, { ...init, headers })
  },
})

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

/** Unwrap a Worker response: parsed JSON on 2xx, ApiError with the Worker's message otherwise. */
export async function unwrap<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T
  let message = `Request failed (${res.status})`
  try {
    const body = (await res.json()) as { error?: string }
    if (body.error) message = body.error
  } catch {
    // keep the generic message
  }
  throw new ApiError(message, res.status)
}

/** POST a raw image to /api/uploads and return the R2 key to attach to a report. */
export async function uploadPhoto(
  blob: Blob,
  turnstileToken?: string
): Promise<string> {
  const token = await tokenProvider()
  const headers: Record<string, string> = {
    "Content-Type": blob.type || "image/jpeg",
  }
  if (token) headers.Authorization = `Bearer ${token}`
  if (turnstileToken) headers["X-Turnstile-Token"] = turnstileToken
  const res = await fetch(`${BASE}/api/uploads`, {
    method: "POST",
    headers,
    body: blob,
  })
  return (await unwrap<{ key: string }>(res)).key
}

/** Fetch a moderator-only report photo as a blob URL. */
export async function adminPhotoUrl(key: string): Promise<string> {
  const token = await tokenProvider()
  const res = await fetch(
    `${BASE}/api/admin/photos/${key.replace(/^reports\//, "")}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  )
  if (!res.ok) throw new ApiError("Photo unavailable", res.status)
  return URL.createObjectURL(await res.blob())
}
