import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useMemo } from "react"
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom"
import { ThemeProvider } from "styled-components"
import ApiExample from "./components/ApiExample"
import ErrorToast from "./components/ErrorToast/ErrorToast"
import { AppProvider, useApp } from "./contexts/AppContext"
import BenchDetailPage from "./pages/BenchDetailPage"
import CardsPage from "./pages/CardsPage"
import MapPage from "./pages/MapPage"
import MobileMapPage from "./pages/MobileMapPage"
import ReportMissingBenchPage from "./pages/ReportMissingBenchPage"
import GlobalStyles from "./styles/GlobalStyles"
import { theme } from "./styles/theme"
import { isMobileDevice } from "./utils/deviceDetection"

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 2,
    },
  },
})

// Component to handle error display
const AppWithErrorHandling = () => {
  const { state, clearError } = useApp()
  const isMobile = useMemo(() => isMobileDevice(), [])

  return (
    <>
      <Router>
        <Routes>
          <Route
            path="/"
            element={
              <Navigate
                to={isMobile ? "/mobile-map" : "/cards"}
                replace
              />
            }
          />
          <Route path="/mobile-map" element={<MobileMapPage />} />
          <Route path="/cards" element={<CardsPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/bench/:id" element={<BenchDetailPage />} />
          <Route
            path="/report-missing-bench"
            element={<ReportMissingBenchPage />}
          />
          <Route path="/api-demo" element={<ApiExample />} />
        </Routes>
      </Router>
      {state.error && <ErrorToast error={state.error} onClose={clearError} />}
    </>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <GlobalStyles />
        <AppProvider>
          <AppWithErrorHandling />
        </AppProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
