import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { lazy, Suspense, useEffect, useRef } from "react"
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom"
import { UsernameDialog } from "./components/account/UsernameDialog"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { AuthProvider } from "./lib/auth"
import "./styles/account.css"

const HomePage = lazy(() => import("./pages/HomePage"))
const MePage = lazy(() => import("./pages/MePage"))
const PublicPage = lazy(() => import("./pages/PublicPage"))
const AdminPage = lazy(() => import("./pages/AdminPage"))
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"))

/** Old bench-page links open the bench on the map instead. */
function BenchRedirect() {
  const { id } = useParams()
  return <Navigate to={`/?bench=${encodeURIComponent(id ?? "")}`} replace />
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

/**
 * After a client-side navigation, move focus to the new page's h1 so keyboard
 * and screen-reader users land on the content, not on <body>. Pages load
 * lazily and the bench page renders its h1 after data arrives, so wait for it.
 */
function RouteFocus() {
  const { pathname } = useLocation()
  // The path focus was last handled for; the first load keeps the browser's
  // default focus (and StrictMode's effect re-run sees the same path).
  const handled = useRef(pathname)
  useEffect(() => {
    if (handled.current === pathname) return
    handled.current = pathname
    const focusH1 = () => {
      const h1 = document.querySelector<HTMLElement>("main h1")
      if (!h1) return false
      h1.tabIndex = -1
      h1.focus({ preventScroll: true })
      return true
    }
    if (focusH1()) return
    const obs = new MutationObserver(() => {
      if (focusH1()) obs.disconnect()
    })
    obs.observe(document.body, { childList: true, subtree: true })
    const t = setTimeout(() => obs.disconnect(), 4000)
    return () => {
      obs.disconnect()
      clearTimeout(t)
    }
  }, [pathname])
  return null
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <RouteFocus />
            <UsernameDialog />
            <Suspense fallback={null}>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/bench/:id" element={<BenchRedirect />} />
                <Route path="/me" element={<MePage />} />
                <Route path="/u/:key" element={<PublicPage />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
