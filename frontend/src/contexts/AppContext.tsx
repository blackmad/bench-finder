import React, {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useReducer,
} from "react"
import type {
  BenchListResponse,
  ClusteredBenchListResponse,
  ConfigResponse,
  SearchSummary,
  WebBenchData,
} from "../api"
import { benchApi } from "../services/api"

// App-specific types (not in API)
export interface AppFilters {
  minConfidence: number
  sourceFilter: "all" | "osm" | "mapillary"
  sortBy: "distance" | "confidence" | "images" | "recent"
  startLat: number
  startLng: number
}

export type ViewMode = "cards" | "map"

export interface AppState {
  benches: WebBenchData[]
  filters: AppFilters
  viewMode: ViewMode
  currentPage: number
  loading: boolean
  hasMore: boolean
  selectedBenchId: number | null
  debugMode: boolean
  config: ConfigResponse | null
  searches: SearchSummary[]
}

// Action types
type AppAction =
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_BENCHES"; payload: WebBenchData[] }
  | { type: "ADD_BENCHES"; payload: WebBenchData[] }
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
        benches: Array.isArray(action.payload) ? action.payload : [],
        currentPage: 0,
      }

    case "ADD_BENCHES":
      return {
        ...state,
        benches: [
          ...(state.benches || []),
          ...(Array.isArray(action.payload) ? action.payload : []),
        ],
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
  feelingLucky: () => Promise<WebBenchData | null>
}

// Create context
const AppContext = createContext<AppContextType | undefined>(undefined)

// Provider component
interface AppProviderProps {
  children: ReactNode
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, {
    ...initialState,
    benches: initialState.benches || [], // Extra safeguard
  })

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
  const updateFilters = useCallback((filters: Partial<AppFilters>) => {
    dispatch({ type: "SET_FILTERS", payload: filters })
    dispatch({ type: "RESET_BENCHES" })
  }, [])

  const loadMoreBenches = useCallback(async (): Promise<void> => {
    if (state.loading || !state.hasMore) return

    try {
      dispatch({ type: "SET_LOADING", payload: true })

      let response: BenchListResponse | ClusteredBenchListResponse
      if (state.filters.sourceFilter === "all") {
        response = await benchApi.getBenches({
          page: state.currentPage,
          page_size: state.config?.page_size || 20,
          min_confidence: state.filters.minConfidence,
          start_lat: state.filters.startLat,
          start_lng: state.filters.startLng,
          sort_by: state.filters.sortBy,
          clustered: false, // For the main app, we want individual benches
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

      // Handle both response types
      let benches: WebBenchData[]
      let hasNext: boolean
      
      if ("benches" in response) {
        // BenchListResponse
        benches = Array.isArray(response.benches) ? response.benches : []
        hasNext = response.pagination.has_next
      } else {
        // ClusteredBenchListResponse - extract individual benches from clusters
        benches = response.clustered_benches?.flatMap(cluster => cluster.all_benches) || []
        hasNext = response.pagination.has_next
      }

      if (state.currentPage === 0) {
        dispatch({ type: "SET_BENCHES", payload: benches })
      } else {
        dispatch({ type: "ADD_BENCHES", payload: benches })
      }

      dispatch({ type: "SET_CURRENT_PAGE", payload: state.currentPage + 1 })
      dispatch({ type: "SET_HAS_MORE", payload: hasNext })
    } catch (error) {
      console.error("Error loading benches:", error)
    } finally {
      dispatch({ type: "SET_LOADING", payload: false })
    }
  }, [
    state.loading,
    state.hasMore,
    state.currentPage,
    state.filters,
    state.config,
  ])

  const resetAndReload = useCallback(async () => {
    dispatch({ type: "RESET_BENCHES" })
    // Trigger a reload of benches after reset
    await loadMoreBenches()
  }, [loadMoreBenches])

  const setUserLocation = useCallback((lat: number, lng: number) => {
    dispatch({ type: "UPDATE_LOCATION", payload: { lat, lng } })
  }, [])

  const feelingLucky = useCallback(async (): Promise<WebBenchData | null> => {
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
  }, [
    state.filters.minConfidence,
    state.filters.sortBy,
    state.filters.sourceFilter,
  ])

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
