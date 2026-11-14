import { hc } from "hono/client"
import type { AppType } from "./worker-types"

/** Typed client for the Worker's /api routes (user writes only). */
export const api = hc<AppType>(import.meta.env.VITE_API_BASE_URL ?? "")
