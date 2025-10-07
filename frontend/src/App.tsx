import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom"
import { ThemeProvider } from "styled-components"
import ApiExample from "./components/ApiExample"
import { AppProvider } from "./contexts/AppContext"
import { AuthProvider } from "./contexts/AuthContext"
import CardsPage from "./pages/CardsPage"
import MapPage from "./pages/MapPage"
import ProfilePage from "./pages/ProfilePage"
import GlobalStyles from "./styles/GlobalStyles"
import { theme } from "./styles/theme"

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 2,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <GlobalStyles />
        <AuthProvider>
          <AppProvider>
            <Router>
              <Routes>
                <Route path="/" element={<Navigate to="/cards" replace />} />
                <Route path="/cards" element={<CardsPage />} />
                <Route path="/map" element={<MapPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/api-demo" element={<ApiExample />} />
              </Routes>
            </Router>
          </AppProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
