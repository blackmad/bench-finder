import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Route, BrowserRouter as Router, Routes } from "react-router-dom"
import { ThemeProvider } from "styled-components"
import { AppProvider } from "./contexts/AppContext"
import HomePage from "./pages/HomePage"
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
        <AppProvider>
          <Router>
            <Routes>
              <Route path="/" element={<HomePage />} />
            </Routes>
          </Router>
        </AppProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
