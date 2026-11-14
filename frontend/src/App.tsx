import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { AuthProvider } from "./lib/auth"
import "./styles/account.css"

const HomePage = lazy(() => import("./pages/HomePage"))
const BenchPage = lazy(() => import("./pages/BenchPage"))
const MePage = lazy(() => import("./pages/MePage"))
const AdminPage = lazy(() => import("./pages/AdminPage"))
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"))

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={null}>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/bench/:id" element={<BenchPage />} />
                <Route path="/me" element={<MePage />} />
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
