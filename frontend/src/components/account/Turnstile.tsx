import { useEffect, useRef } from "react"

interface TurnstileApi {
  render: (
    el: HTMLElement,
    opts: {
      sitekey: string
      action?: string
      callback: (token: string) => void
      "expired-callback": () => void
      "error-callback": () => void
    }
  ) => string
  remove: (id: string) => void
}
declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

const SCRIPT =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
let scriptPromise: Promise<void> | null = null
function loadScript(): Promise<void> {
  scriptPromise ??= new Promise((resolve, reject) => {
    const s = document.createElement("script")
    s.src = SCRIPT
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error("Turnstile failed to load"))
    document.head.appendChild(s)
  })
  return scriptPromise
}

export const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY

/**
 * Anti-spam widget for anonymous submissions. Change `resetKey` to get a fresh
 * single-use token. Renders an explanation when no site key is configured.
 */
export function Turnstile({
  onToken,
  resetKey,
}: {
  onToken: (token: string | null) => void
  resetKey: number
}) {
  const host = useRef<HTMLDivElement>(null)
  const cb = useRef(onToken)
  cb.current = onToken

  // biome-ignore lint/correctness/useExhaustiveDependencies: resetKey re-renders the widget on purpose
  useEffect(() => {
    if (!turnstileSiteKey || !host.current) return
    const el = host.current
    let id: string | undefined
    let cancelled = false
    cb.current(null)
    loadScript()
      .then(() => {
        if (cancelled || !window.turnstile) return
        id = window.turnstile.render(el, {
          sitekey: turnstileSiteKey,
          // Must match TURNSTILE_ACTION in worker/src/turnstile.ts.
          action: "report",
          callback: (t) => cb.current(t),
          "expired-callback": () => cb.current(null),
          "error-callback": () => cb.current(null),
        })
      })
      .catch(() => cb.current(null))
    return () => {
      cancelled = true
      if (id) window.turnstile?.remove(id)
    }
  }, [resetKey])

  if (!turnstileSiteKey) {
    return (
      <p className="form-note">
        {import.meta.env.DEV
          ? "Turnstile is not configured (VITE_TURNSTILE_SITE_KEY is unset), so anonymous reports will be refused."
          : "Reports from visitors who are not signed in are paused right now."}{" "}
        Signing in lets you send one.
      </p>
    )
  }
  return <div ref={host} className="turnstile" />
}
