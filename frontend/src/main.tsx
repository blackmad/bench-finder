import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import App from "./App.tsx"
import "./styles/index.css"

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
