import * as Sentry from "@sentry/react"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import App from "./App.tsx"
import "./styles/index.css"

// Errors only (no tracing, no replay, no personal data) from the live site.
if (import.meta.env.PROD) {
  Sentry.init({
    dsn: "https://b801bbd46738a657a8f7cf5906ad2ffe@o417464.ingest.us.sentry.io/4512443395604480",
    release: import.meta.env.VITE_SENTRY_RELEASE,
    sendDefaultPii: false,
    allowUrls: [/bench\.blackmad\.com/, /workers\.dev/],
    // Stale chunks after a deploy reload themselves; not worth an alert.
    ignoreErrors: [
      /dynamically imported module/,
      /Importing a module script failed/,
    ],
  })
}

const root = document.getElementById("root")
if (!root) throw new Error("#root missing")

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>
)

// A tab opened before a deploy asks for chunks that are gone: reload once.
window.addEventListener("vite:preloadError", (e) => {
  try {
    if (sessionStorage.getItem("bf-chunk-reload")) return
    sessionStorage.setItem("bf-chunk-reload", "1")
  } catch {
    return
  }
  e.preventDefault()
  window.location.reload()
})
// Once a page has run for a while, the next stale chunk may reload again.
setTimeout(() => {
  try {
    sessionStorage.removeItem("bf-chunk-reload")
  } catch {
    /* storage blocked */
  }
}, 15_000)
