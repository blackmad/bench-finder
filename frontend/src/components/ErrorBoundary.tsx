import { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
}
interface State {
  failed: boolean
}

const STALE_CHUNK =
  /dynamically imported module|Importing a module script failed|Failed to fetch|error loading dynamically/i
const RELOADED = "bf-chunk-reload"

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
    // After a deploy, an open tab asks for code chunks that no longer exist.
    // Reload once to pick up the new build instead of showing the error.
    if (STALE_CHUNK.test(String(error?.message))) {
      try {
        if (!sessionStorage.getItem(RELOADED)) {
          sessionStorage.setItem(RELOADED, "1")
          window.location.reload()
        }
      } catch {
        /* storage blocked: show the error with its Reload button */
      }
    }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <main className="mx-auto max-w-[640px] px-4 py-16" role="alert">
        <h1 className="mb-3 text-[28px] leading-tight font-bold [font-variation-settings:'wdth'_112]">
          Something went wrong
        </h1>
        <p className="mb-6 text-ink-2">
          This page failed to load. Reloading usually fixes it.
        </p>
        <button
          type="button"
          className="border-[1.5px] border-ink bg-card px-3.5 py-2 font-semibold hover:bg-ink hover:text-card"
          onClick={() => window.location.reload()}
        >
          Reload
        </button>
      </main>
    )
  }
}
