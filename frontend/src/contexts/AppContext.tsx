import React, {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useReducer,
} from "react"
import { benchApi } from "../services/api"
import type {
  AppFilters,
  AppState,
  Bench,
  BenchListResponse,
  ConfigResponse,
  SearchSummary,
  ViewMode,
} from "../types"

// Action types
type AppAction =
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_BENCHES"; payload: Bench[] }
  | { type: "ADD_BENCHES"; payload: Bench[] }
  | { type: "SET_FILTERS"; payload: Partial<AppFilters> }
  | { type: "SET_VIEW_MODE"; payload: ViewMode }
  | { type: "SET_CURRENT_PAGE"; payload: number }
  | { type: "SET_HAS_MORE"; payload: boolean }
  | { type: "SET_SELECTED_BENCH"; payload: number | null }
  | { type: "TOGGLE_DEBUG_MODE" }
  | { type: "SET_CONFIG"; payload: ConfigResponse }
  | { type: "SET_SEARCHES"; payload: SearchSummary[] }
  | { type: "RESET_BENCHES" }
  | { type: "UPDATE_LOCATION"; payload: { lat: number; lng: number } }

// Initial state
const initialState: AppState = {
  benches: [],
  filters: {
    minConfidence: 0.2,
    sourceFilter: "all",
    sortBy: "distance",
    startLat: 52.3613577, // Amsterdam default
    startLng: 4.8666322,
  },
  viewMode: "cards",
  currentPage: 0,
  loading: false,
  hasMore: true,
  selectedBenchId: null,
  debugMode: false,
  config: null,
  searches: [],
}

// Reducer function
const appReducer = (state: AppState, action: AppAction): AppState => {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, loading: action.payload }

    case "SET_BENCHES":
      return {
        ...state,
        benches: action.payload,
        currentPage: 0,
      }

    case "ADD_BENCHES":
      return {
        ...state,
        benches: [...state.benches, ...action.payload],
      }

    case "SET_FILTERS":
      return {
        ...state,
        filters: { ...state.filters, ...action.payload },
      }

    case "SET_VIEW_MODE":
      return { ...state, viewMode: action.payload }

    case "SET_CURRENT_PAGE":
      return { ...state, currentPage: action.payload }

    case "SET_HAS_MORE":
      return { ...state, hasMore: action.payload }

    case "SET_SELECTED_BENCH":
      return { ...state, selectedBenchId: action.payload }

    case "TOGGLE_DEBUG_MODE":
      return { ...state, debugMode: !state.debugMode }

    case "SET_CONFIG":
      return {
        ...state,
        config: action.payload,
        filters: {
          ...state.filters,
          minConfidence: action.payload.default_min_confidence,
          startLat: action.payload.default_start_lat,
          startLng: action.payload.default_start_lng,
        },
      }

    case "SET_SEARCHES":
      return { ...state, searches: action.payload }

    case "RESET_BENCHES":
      return {
        ...state,
        benches: [],
        currentPage: 0,
        hasMore: true,
      }

    case "UPDATE_LOCATION":
      return {
        ...state,
        filters: {
          ...state.filters,
          startLat: action.payload.lat,
          startLng: action.payload.lng,
        },
      }

    default:
      return state
  }
}

// Context interface
interface AppContextType {
  state: AppState
  dispatch: React.Dispatch<AppAction>
  // Helper functions
  updateFilters: (filters: Partial<AppFilters>) => void
  resetAndReload: () => Promise<void>
  loadMoreBenches: () => Promise<void>
  setUserLocation: (lat: number, lng: number) => void
  feelingLucky: () => Promise<Bench | null>
}

// Create context
const AppContext = createContext<AppContextType | undefined>(undefined)

// Provider component
interface AppProviderProps {
  children: ReactNode
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState)

  // Initialize app data
  useEffect(() => {
    const initializeApp = async () => {
      try {
        dispatch({ type: "SET_LOADING", payload: true })

        // Load configuration
        const config = await benchApi.getConfig()
        dispatch({ type: "SET_CONFIG", payload: config })

        // Load available searches
        const searchesResponse = await benchApi.getSearches()
        dispatch({ type: "SET_SEARCHES", payload: searchesResponse.searches })

        // Try to get user's current location
        if ("geolocation" in navigator) {
          navigator.geolocation.getCurrentPosition(
            (position) => {
              dispatch({
                type: "UPDATE_LOCATION",
                payload: {
                  lat: position.coords.latitude,
                  lng: position.coords.longitude,
                },
              })
            },
            (error) => {
              console.warn("Geolocation failed:", error)
              // Use default location from config
            },
            {
              enableHighAccuracy: true,
              timeout: 10000,
              maximumAge: 300000, // 5 minutes
            }
          )
        }
      } catch (error) {
        console.error("Failed to initialize app:", error)

        // Don't automatically load benches here - let the HomePage handle it
      } finally {
        dispatch({ type: "SET_LOADING", payload: false })
      }
    }

    initializeApp()
  }, [])

  // Helper functions
  const updateFilters = (filters: Partial<AppFilters>) => {
    dispatch({ type: "SET_FILTERS", payload: filters })
    dispatch({ type: "RESET_BENCHES" })
  }

  const resetAndReload = async () => {
    dispatch({ type: "RESET_BENCHES" })
    // Trigger a reload of benches after reset
    await loadMoreBenches()
  }

  const loadMoreBenches = async (): Promise<void> => {
    if (state.loading || !state.hasMore) return

    try {
      dispatch({ type: "SET_LOADING", payload: true })

      let response: BenchListResponse
      if (state.filters.sourceFilter === "all") {
        response = await benchApi.getBenches({
          page: state.currentPage,
          page_size: state.config?.page_size || 20,
          min_confidence: state.filters.minConfidence,
          start_lat: state.filters.startLat,
          start_lng: state.filters.startLng,
          sort_by: state.filters.sortBy,
        })
      } else {
        response = await benchApi.getBenchesBySource(
          state.filters.sourceFilter,
          {
            page: state.currentPage,
            page_size: state.config?.page_size || 20,
            min_confidence: state.filters.minConfidence,
            start_lat: state.filters.startLat,
            start_lng: state.filters.startLng,
            sort_by: state.filters.sortBy,
          }
        )
      }

      if (state.currentPage === 0) {
        dispatch({ type: "SET_BENCHES", payload: response.benches })
      } else {
        dispatch({ type: "ADD_BENCHES", payload: response.benches })
      }

      dispatch({ type: "SET_CURRENT_PAGE", payload: state.currentPage + 1 })
      dispatch({ type: "SET_HAS_MORE", payload: response.pagination.has_next })
    } catch (error) {
      console.error("Error loading benches:", error)
    } finally {
      dispatch({ type: "SET_LOADING", payload: false })
    }
  }

  const setUserLocation = (lat: number, lng: number) => {
    dispatch({ type: "UPDATE_LOCATION", payload: { lat, lng } })
  }

  const feelingLucky = async (): Promise<Bench | null> => {
    try {
      const params: any = {
        min_confidence: state.filters.minConfidence,
        sort_by: state.filters.sortBy,
      }

      if (state.filters.sourceFilter !== "all") {
        params.source = state.filters.sourceFilter
      }

      const response = await benchApi.getRandomBench(params)
      return response.bench
    } catch (error) {
      console.error("Error getting random bench:", error)
      return null
    }
  }

  const contextValue: AppContextType = {
    state,
    dispatch,
    updateFilters,
    resetAndReload,
    loadMoreBenches,
    setUserLocation,
    feelingLucky,
  }

  return (
    <AppContext.Provider value={contextValue}>{children}</AppContext.Provider>
  )
}

// Hook to use the context
export const useApp = (): AppContextType => {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error("useApp must be used within an AppProvider")
  }
  return context
}

export default AppContext
