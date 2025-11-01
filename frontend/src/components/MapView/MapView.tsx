import { divIcon, type LatLngBounds } from "leaflet"
import type React from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet"
import { Link, useSearchParams } from "react-router-dom"
import styled from "styled-components"
import "leaflet/dist/leaflet.css"
import "../../utils/leafletFix"
import type { BboxBenchResponse, BenchMode, WebBenchData } from "../../api"
import { useApp } from "../../contexts/AppContext"
import { benchApi } from "../../services/api"
import LoadingSpinner from "../LoadingSpinner/LoadingSpinner"
import Modal from "../Modal/Modal"
import ReportModal from "../ReportModal/ReportModal"

const MapViewContainer = styled.div`
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  overflow: hidden; /* Prevent container scrolling */
  background: #f0f0f0;
`

const MainMap = styled.div`
  flex: 1;
  height: 100%;
  position: relative;
  background: #e0e0e0;
  overflow: hidden; /* Pin map - prevent scrolling */
  min-width: 0; /* Allow flex shrinking */
  min-height: 0; /* Allow flex shrinking */

  /* Ensure Leaflet container fills parent */
  .leaflet-container {
    height: 100% !important;
    width: 100% !important;
    overflow: hidden !important;
  }

  /* Prevent Leaflet from causing page scroll */
  .leaflet-pane {
    position: absolute;
  }
`

const MapSidebar = styled.div`
  width: 400px;
  background: ${({ theme }) => theme.colors.background};
  border-left: 1px solid ${({ theme }) => theme.colors.border};
  display: flex;
  flex-direction: column;
  overflow: hidden;

  @media (max-width: ${({ theme }) => theme.breakpoints.md}) {
    width: 100%;
    height: 40%;
    border-left: none;
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }
`

const SidebarHeader = styled.div`
  padding: ${({ theme }) => theme.spacing[5]};
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
  background: ${({ theme }) => theme.colors.backgroundTertiary};

  h3 {
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
    color: ${({ theme }) => theme.colors.textPrimary};
    font-size: ${({ theme }) => theme.typography.sizes.xl};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
  }
`

const SidebarStats = styled.div`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
`

const SidebarContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 0;
`

const SidebarPlaceholder = styled.div`
  padding: ${({ theme }) => theme.spacing[10]} ${({ theme }) => theme.spacing[5]};
  text-align: center;
  color: ${({ theme }) => theme.colors.textSecondary};

  .icon {
    font-size: ${({ theme }) => theme.typography.sizes["4xl"]};
    margin-bottom: ${({ theme }) => theme.spacing[4]};
    opacity: 0.7;
  }

  p {
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
    font-size: ${({ theme }) => theme.typography.sizes.base};
  }

  small {
    color: ${({ theme }) => theme.colors.textTertiary};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
  }
`

const SidebarLoading = styled.div`
  padding: ${({ theme }) => theme.spacing[8]};
  text-align: center;
  background: ${({ theme }) => theme.colors.backgroundTertiary};

  p {
    margin: ${({ theme }) => theme.spacing[4]} 0 0 0;
    color: ${({ theme }) => theme.colors.textSecondary};
  }
`

const MapBenchCard = styled.div<{ $selected?: boolean; $hovered?: boolean }>`
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
  padding: ${({ theme }) => theme.spacing[4]};
  cursor: pointer;
  transition: background-color ${({ theme }) => theme.transitions.fast};
  display: flex;
  gap: ${({ theme }) => theme.spacing[4]};
  background: ${({ $selected, $hovered, theme }) =>
    $selected
      ? `${theme.colors.primary}10`
      : $hovered
        ? `${theme.colors.primary}08`
        : "transparent"};
  border-left: ${({ $selected, $hovered, theme }) =>
    $selected
      ? `3px solid ${theme.colors.primary}`
      : $hovered
        ? `3px solid ${theme.colors.primary}80`
        : "3px solid transparent"};

  &:hover {
    background: ${({ theme }) => `${theme.colors.primary}08`};
  }
`

const MapCardImage = styled.div`
  width: 180px;
  height: 120px;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  overflow: hidden;
  flex-shrink: 0;
  background: ${({ theme }) => theme.colors.gray100};

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
    color: ${({ theme }) => theme.colors.gray400};
  }
`

const MapCardContent = styled.div`
  flex: 1;
  min-width: 0;
`

const MapCardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: ${({ theme }) => theme.spacing[2]};
`

const MapCardTitle = styled.div`
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  line-height: ${({ theme }) => theme.typography.lineHeights.tight};
`

const MapCardTitleLink = styled(Link)`
  color: inherit;
  text-decoration: none;
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }
`

const PopupTitleLink = styled(Link)`
  color: inherit;
  text-decoration: none;
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }
`

const MapCardConfidence = styled.div<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "block" : "none")};
  background: ${({ theme }) => theme.colors.success};
  color: white;
  padding: 2px ${({ theme }) => theme.spacing[2]};
  border-radius: ${({ theme }) => theme.borderRadius.base};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  white-space: nowrap;
`

const MapCardMeta = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[3]};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-top: ${({ theme }) => theme.spacing[1]};

  span {
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing[1]};
  }
`

const SearchButton = styled.button`
  position: absolute;
  top: ${({ theme }) => theme.spacing[5]};
  right: ${({ theme }) => theme.spacing[5]};
  z-index: 1000;
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
  border: none;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  cursor: pointer;
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  transition: background ${({ theme }) => theme.transitions.fast};
  box-shadow: ${({ theme }) => theme.shadows.lg};
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};

  &:hover {
    background: ${({ theme }) => theme.colors.primaryDark};
  }

  @media (max-width: ${({ theme }) => theme.breakpoints.md}) {
    top: ${({ theme }) => theme.spacing[3]};
    right: ${({ theme }) => theme.spacing[3]};
  }
`

const MapLoadingOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(2px);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
`

const LoadingContent = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[4]};
  color: white;
  text-align: center;
`

const LoadingText = styled.div`
  font-size: ${({ theme }) => theme.typography.sizes.base};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  color: white;
`

// Component to handle map events
const MapEventHandler: React.FC<{
  onBoundsChange: (bounds: LatLngBounds) => void
  onViewChange: (center: [number, number], zoom: number) => void
  isUpdatingFromUrl: React.MutableRefObject<boolean>
  onUserInteraction: () => void
}> = ({
  onBoundsChange,
  onViewChange,
  isUpdatingFromUrl,
  onUserInteraction,
}) => {
  const map = useMap()

  // Use refs to keep callbacks stable
  const onBoundsChangeRef = useRef(onBoundsChange)
  const onViewChangeRef = useRef(onViewChange)

  // Update refs when callbacks change
  useEffect(() => {
    onBoundsChangeRef.current = onBoundsChange
    onViewChangeRef.current = onViewChange
  }, [onBoundsChange, onViewChange])

  useEffect(() => {
    const handleMoveEnd = () => {
      // Skip if this is from a programmatic update
      if (isUpdatingFromUrl.current) {
        return
      }
      const bounds = map.getBounds()
      onBoundsChangeRef.current(bounds)
      // Only trigger view change if user actually moved the map
      // Small delay to ensure this isn't from our own setView call
      setTimeout(() => {
        if (!isUpdatingFromUrl.current) {
          // Get fresh values inside timeout to avoid stale closures
          const center = map.getCenter()
          const zoom = map.getZoom()
          onViewChangeRef.current([center.lat, center.lng], zoom)
          // Mark that user has interacted with the map
          onUserInteraction()
        }
      }, 50)
    }

    const handleZoomEnd = () => {
      // Skip if this is from a programmatic update
      if (isUpdatingFromUrl.current) {
        return
      }
      // Small delay to ensure this isn't from our own setView call
      setTimeout(() => {
        if (!isUpdatingFromUrl.current) {
          // Get fresh values inside timeout to avoid stale closures
          const center = map.getCenter()
          const zoom = map.getZoom()
          onViewChangeRef.current([center.lat, center.lng], zoom)
          // Mark that user has interacted with the map
          onUserInteraction()
        }
      }, 50)
    }

    map.on("moveend", handleMoveEnd)
    map.on("zoomend", handleZoomEnd)

    // Trigger map resize after mount to ensure proper rendering
    setTimeout(() => {
      map.invalidateSize()
    }, 100)

    // Initial bounds and view - but skip URL update
    setTimeout(() => {
      const bounds = map.getBounds()
      onBoundsChangeRef.current(bounds)
      // Don't call onViewChange on initial mount to avoid URL updates
    }, 200)

    return () => {
      map.off("moveend", handleMoveEnd)
      map.off("zoomend", handleZoomEnd)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, onUserInteraction, isUpdatingFromUrl.current]) // Only depend on map instance, callbacks accessed via refs

  return null
}

// Component to programmatically update map view from URL
const MapViewUpdater: React.FC<{
  center: [number, number]
  zoom: number
  isUpdatingFromUrl: React.MutableRefObject<boolean>
}> = ({ center, zoom, isUpdatingFromUrl }) => {
  const map = useMap()
  const lastCenterRef = useRef<[number, number] | null>(null)
  const lastZoomRef = useRef<number | null>(null)

  useEffect(() => {
    const currentCenter = map.getCenter()
    const currentZoom = map.getZoom()

    // Check if the requested view is significantly different from current map state
    const centerChanged =
      Math.abs(currentCenter.lat - center[0]) > 0.0001 ||
      Math.abs(currentCenter.lng - center[1]) > 0.0001
    const zoomChanged = Math.abs(currentZoom - zoom) > 0.1

    // Also check if this is different from what we last set (to avoid loops)
    const isDifferentFromLast =
      !lastCenterRef.current ||
      !lastZoomRef.current ||
      Math.abs(lastCenterRef.current[0] - center[0]) > 0.0001 ||
      Math.abs(lastCenterRef.current[1] - center[1]) > 0.0001 ||
      Math.abs(lastZoomRef.current - zoom) > 0.1

    // Only update if both the map needs updating AND the values are different from last update
    if ((centerChanged || zoomChanged) && isDifferentFromLast) {
      // Set flag before updating to prevent URL updates
      isUpdatingFromUrl.current = true
      lastCenterRef.current = center
      lastZoomRef.current = zoom

      map.setView(center, zoom, { animate: false })

      // Reset flag after map has updated (events fire asynchronously)
      // Use a longer timeout to ensure moveend/zoomend events have fired
      setTimeout(() => {
        isUpdatingFromUrl.current = false
      }, 600)
    } else if (!centerChanged && !zoomChanged) {
      // Map is already at the correct position, just update our refs without moving
      lastCenterRef.current = center
      lastZoomRef.current = zoom
    }
  }, [
    map,
    center,
    zoom, // Set flag before updating to prevent URL updates
    isUpdatingFromUrl,
  ])

  return null
}

// Component to capture map instance for search button
const MapInstanceCapture: React.FC<{
  mapRef: React.MutableRefObject<any>
}> = ({ mapRef }) => {
  const map = useMap()
  useEffect(() => {
    mapRef.current = map
  }, [map, mapRef])
  return null
}

// Component to trigger search when filters change
const FilterChangeHandler: React.FC<{
  onBoundsChange: (bounds: LatLngBounds) => void
  filters: {
    mode: BenchMode
    minConfidence: number
    sortBy: string
    sourceFilter: string
  }
}> = ({ onBoundsChange, filters }) => {
  const map = useMap()
  const lastFiltersRef = useRef(filters)
  const isFirstMountRef = useRef(true)

  useEffect(() => {
    // Skip on initial mount - let the initial bounds change handler trigger the first search
    if (isFirstMountRef.current) {
      isFirstMountRef.current = false
      lastFiltersRef.current = filters
      return
    }

    // Check if filters have changed
    const filtersChanged =
      lastFiltersRef.current.mode !== filters.mode ||
      lastFiltersRef.current.minConfidence !== filters.minConfidence ||
      lastFiltersRef.current.sortBy !== filters.sortBy ||
      lastFiltersRef.current.sourceFilter !== filters.sourceFilter

    if (filtersChanged) {
      lastFiltersRef.current = filters
      // Trigger a search with current map bounds when filters change
      const bounds = map.getBounds()
      if (bounds.isValid()) {
        onBoundsChange(bounds)
      }
    }
  }, [filters, map, onBoundsChange])

  return null
}

interface MapData {
  benches: WebBenchData[]
  totalCount: number
}

const MapView: React.FC = () => {
  const { state } = useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const [mapData, setMapData] = useState<MapData>({
    benches: [],
    totalCount: 0,
  })
  const [selectedBenchId, setSelectedBenchId] = useState<number | null>(null)
  const [hoveredBenchId, setHoveredBenchId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [showSearchButton, setShowSearchButton] = useState(false)
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const urlUpdateTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isUpdatingFromUrlRef = useRef(false)
  const mapRef = useRef<any>(null)

  // Modal state
  const [selectedBench, setSelectedBench] = useState<WebBenchData | null>(null)
  const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null)
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [currentModalIndex, setCurrentModalIndex] = useState(0)
  const [isReportModalOpen, setIsReportModalOpen] = useState(false)

  const searchMapArea = useCallback(
    async (bounds?: LatLngBounds) => {
      if (!bounds) return

      setLoading(true)
      try {
        const params = {
          north: bounds.getNorth(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          west: bounds.getWest(),
          min_confidence: state.filters.minConfidence,
          limit: 200,
          sort_by: state.filters.sortBy,
          mode: state.filters.mode,
        }

        // Include source filter (defaults to OSM, None for all sources)
        ;(params as any).source =
          state.filters.sourceFilter !== "all"
            ? state.filters.sourceFilter
            : null

        const response = await benchApi.getBenchesInBbox(params)

        // Handle individual bench response
        const individualResponse = response as BboxBenchResponse
        setMapData({
          benches: individualResponse.benches as WebBenchData[],
          totalCount:
            individualResponse.total_count || individualResponse.benches.length,
        })
      } catch (error) {
        console.error("Map search failed:", error)
        setMapData({ benches: [], totalCount: 0 })
      } finally {
        setLoading(false)
      }
    },
    [
      state.filters.minConfidence,
      state.filters.sortBy,
      state.filters.sourceFilter,
      state.filters.mode,
    ]
  )

  const handleBoundsChange = useCallback(
    async (bounds: LatLngBounds) => {
      // Clear previous timeout
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }

      // Debounce the search
      searchTimeoutRef.current = setTimeout(async () => {
        await searchMapArea(bounds)
      }, 500)
    },
    [searchMapArea]
  )

  const handleSearchHere = useCallback(() => {
    if (!mapRef.current) return
    const bounds = mapRef.current.getBounds()
    if (bounds?.isValid()) {
      searchMapArea(bounds)
      setShowSearchButton(false)
    }
  }, [searchMapArea])

  const handleBenchClick = useCallback(
    (benchId: number) => {
      setSelectedBenchId(benchId)

      // Find the bench in the list and open modal
      const bench = mapData.benches.find((b) => b.id === benchId)
      if (bench) {
        const benchIndex = mapData.benches.findIndex((b) => b.id === benchId)
        const imageUrl = bench.image_filenames?.[0]
          ? `/images/${bench.image_filenames[0]}`
          : null
        const imageId = bench.image_ids?.[0] || null

        setSelectedBench(bench)
        setSelectedImageUrl(imageUrl)
        setSelectedImageId(imageId)
        setCurrentModalIndex(benchIndex >= 0 ? benchIndex : 0)
        setModalOpen(true)
      }
    },
    [mapData.benches]
  )

  const handleModalClose = useCallback(() => {
    setModalOpen(false)
    setSelectedBench(null)
    setSelectedImageUrl(null)
    setSelectedImageId(null)
    setCurrentModalIndex(0)
  }, [])

  const handleModalNavigate = useCallback(
    (direction: "prev" | "next") => {
      const benchesForNavigation = mapData.benches

      if (!benchesForNavigation || benchesForNavigation.length === 0) return

      let newIndex =
        direction === "prev" ? currentModalIndex - 1 : currentModalIndex + 1

      // Clamp to valid range
      newIndex = Math.max(
        0,
        Math.min(benchesForNavigation.length - 1, newIndex)
      )

      const newBench = benchesForNavigation[newIndex]
      if (newBench) {
        const imageUrl = newBench.image_filenames?.[0]
          ? `/images/${newBench.image_filenames[0]}`
          : null
        const imageId = newBench.image_ids?.[0] || null

        setSelectedBench(newBench)
        setSelectedImageUrl(imageUrl)
        setSelectedImageId(imageId)
        setCurrentModalIndex(newIndex)
        setSelectedBenchId(newBench.id)
      }
    },
    [currentModalIndex, mapData.benches]
  )

  const handleImageSelect = useCallback(
    (imageUrl: string, imageId: number) => {
      if (!selectedBench) return
      setSelectedImageUrl(imageUrl)
      setSelectedImageId(imageId)
    },
    [selectedBench]
  )

  // Get initial center and zoom from URL or fallback to filters/defaults
  const getInitialCenter = (): [number, number] => {
    const urlLat = searchParams.get("lat")
    const urlLng = searchParams.get("lng")

    if (urlLat && urlLng) {
      const lat = parseFloat(urlLat)
      const lng = parseFloat(urlLng)
      if (!Number.isNaN(lat) && !Number.isNaN(lng)) {
        return [lat, lng]
      }
    }

    return [state.filters.startLat, state.filters.startLng]
  }

  const getInitialZoom = (): number => {
    const urlZoom = searchParams.get("zoom")
    if (urlZoom) {
      const zoom = parseFloat(urlZoom)
      if (!Number.isNaN(zoom) && zoom >= 0 && zoom <= 19) {
        return zoom
      }
    }
    return 13
  }

  const [mapCenter, setMapCenter] = useState<[number, number]>(() =>
    getInitialCenter()
  )
  const [mapZoom, setMapZoom] = useState<number>(() => getInitialZoom())
  const isInitialMountRef = useRef(true)

  // Refs to track current map state without causing re-renders
  const mapCenterRef = useRef<[number, number]>(mapCenter)
  const mapZoomRef = useRef<number>(mapZoom)

  // Keep refs in sync with state
  useEffect(() => {
    mapCenterRef.current = mapCenter
  }, [mapCenter])

  useEffect(() => {
    mapZoomRef.current = mapZoom
  }, [mapZoom])

  // Mark initial mount as complete after a brief delay
  useEffect(() => {
    const timer = setTimeout(() => {
      isInitialMountRef.current = false
    }, 500)
    return () => clearTimeout(timer)
  }, [])

  // Track last URL we set to avoid redundant updates
  const lastSetUrlRef = useRef<string>("")
  // Track last values we set to URL for more robust comparison
  const lastSetValuesRef = useRef<{
    lat: number
    lng: number
    zoom: number
  } | null>(null)

  // Update URL with map view parameters (debounced)
  const updateUrlWithMapView = useCallback(
    (center: [number, number], zoom: number) => {
      if (isUpdatingFromUrlRef.current || isInitialMountRef.current) {
        return
      }

      if (urlUpdateTimeoutRef.current) {
        clearTimeout(urlUpdateTimeoutRef.current)
      }

      urlUpdateTimeoutRef.current = setTimeout(() => {
        // Double-check flag before updating
        if (isUpdatingFromUrlRef.current) {
          return
        }

        // Get fresh searchParams to avoid stale closure issues
        const currentParams = new URLSearchParams(window.location.search)

        // Round to match precision we'll compare against
        const latStr = center[0].toFixed(7)
        const lngStr = center[1].toFixed(7)
        const zoomStr = zoom.toString()
        const latNum = parseFloat(latStr)
        const lngNum = parseFloat(lngStr)
        const zoomNum = parseFloat(zoomStr)

        // Check if values actually changed before updating (compare with last set values)
        if (lastSetValuesRef.current) {
          const valuesChanged =
            Math.abs(lastSetValuesRef.current.lat - latNum) > 0.00001 ||
            Math.abs(lastSetValuesRef.current.lng - lngNum) > 0.00001 ||
            Math.abs(lastSetValuesRef.current.zoom - zoomNum) > 0.1

          if (!valuesChanged) {
            // No change needed - values are the same as what we last set
            return
          }
        }

        // Update lat/lng (these are already used by filters, so we'll update them)
        currentParams.set("lat", latStr)
        currentParams.set("lng", lngStr)

        // Update zoom
        currentParams.set("zoom", zoomStr)

        const newUrlString = currentParams.toString()

        // Only update if URL actually changed
        if (newUrlString !== lastSetUrlRef.current) {
          lastSetUrlRef.current = newUrlString
          lastSetValuesRef.current = { lat: latNum, lng: lngNum, zoom: zoomNum }
          // Mark this URL as the one we're about to set, so we don't process our own update
          lastProcessedUrlRef.current = newUrlString
          setSearchParams(currentParams, { replace: true })
        }
      }, 300) // Debounce to avoid rapid updates
    },
    [setSearchParams]
  )

  // Handle map view changes (zoom/pan)
  const handleViewChange = useCallback(
    (center: [number, number], zoom: number) => {
      setMapCenter(center)
      setMapZoom(zoom)
      updateUrlWithMapView(center, zoom)
    },
    [updateUrlWithMapView]
  )

  // Handle user interaction with map
  const handleUserInteraction = useCallback(() => {
    setShowSearchButton(true)
  }, [])

  // Track the last URL values we processed to avoid processing our own updates
  const lastProcessedUrlRef = useRef<string>("")

  // Sync map with URL changes (but only if not triggered by our own updates)
  useEffect(() => {
    // Skip if we're currently updating from our own action
    if (isUpdatingFromUrlRef.current || isInitialMountRef.current) {
      return
    }

    // Create a string representation of current URL params to detect changes
    const currentUrlParams = searchParams.toString()

    // Skip if this is the same URL we just processed or set
    if (
      currentUrlParams === lastProcessedUrlRef.current ||
      currentUrlParams === lastSetUrlRef.current
    ) {
      return
    }

    const urlLat = searchParams.get("lat")
    const urlLng = searchParams.get("lng")
    const urlZoom = searchParams.get("zoom")

    // Check if URL values differ significantly from current state (using refs to avoid dependency issues)
    // This indicates an external URL change (e.g., browser back/forward, manual URL edit)
    if (urlLat && urlLng && urlZoom) {
      const lat = parseFloat(urlLat)
      const lng = parseFloat(urlLng)
      const zoom = parseFloat(urlZoom)

      // Also check if these are the same values we just set (in case URL string differs due to other params)
      const isSameAsLastSet =
        lastSetValuesRef.current &&
        Math.abs(lastSetValuesRef.current.lat - lat) < 0.00001 &&
        Math.abs(lastSetValuesRef.current.lng - lng) < 0.00001 &&
        Math.abs(lastSetValuesRef.current.zoom - zoom) < 0.1

      // Also check if map params match current map state (filter-only URL changes)
      const matchesCurrentMap =
        Math.abs(lat - mapCenterRef.current[0]) < 0.00001 &&
        Math.abs(lng - mapCenterRef.current[1]) < 0.00001 &&
        Math.abs(zoom - mapZoomRef.current) < 0.1

      if (isSameAsLastSet || matchesCurrentMap) {
        // This is either our own update or only filter params changed - just mark it as processed and skip
        lastProcessedUrlRef.current = currentUrlParams
        return
      }

      if (
        !Number.isNaN(lat) &&
        !Number.isNaN(lng) &&
        !Number.isNaN(zoom) &&
        zoom >= 0 &&
        zoom <= 19 &&
        (Math.abs(lat - mapCenterRef.current[0]) > 0.0001 ||
          Math.abs(lng - mapCenterRef.current[1]) > 0.0001 ||
          Math.abs(zoom - mapZoomRef.current) > 0.1)
      ) {
        // This is an external URL change with different map params - update map view
        lastProcessedUrlRef.current = currentUrlParams
        isUpdatingFromUrlRef.current = true
        setMapCenter([lat, lng])
        setMapZoom(zoom)

        // Reset flag after a delay to allow map to update
        setTimeout(() => {
          isUpdatingFromUrlRef.current = false
          // Hide search button when map is updated programmatically
          setShowSearchButton(false)
        }, 600)
      }
    } else if (urlLat && urlLng) {
      // URL has lat/lng but no zoom - update center only if it differs
      const lat = parseFloat(urlLat)
      const lng = parseFloat(urlLng)

      // Check if these are the same values we just set
      const isSameAsLastSet =
        lastSetValuesRef.current &&
        Math.abs(lastSetValuesRef.current.lat - lat) < 0.00001 &&
        Math.abs(lastSetValuesRef.current.lng - lng) < 0.00001

      // Check if matches current map state
      const matchesCurrentMap =
        Math.abs(lat - mapCenterRef.current[0]) < 0.00001 &&
        Math.abs(lng - mapCenterRef.current[1]) < 0.00001

      if (isSameAsLastSet || matchesCurrentMap) {
        // This is either our own update or only filter params changed - just mark it as processed and skip
        lastProcessedUrlRef.current = currentUrlParams
        return
      }

      if (
        !Number.isNaN(lat) &&
        !Number.isNaN(lng) &&
        (Math.abs(lat - mapCenterRef.current[0]) > 0.0001 ||
          Math.abs(lng - mapCenterRef.current[1]) > 0.0001)
      ) {
        lastProcessedUrlRef.current = currentUrlParams
        isUpdatingFromUrlRef.current = true
        setMapCenter([lat, lng])
        setTimeout(() => {
          isUpdatingFromUrlRef.current = false
          // Hide search button when map is updated programmatically
          setShowSearchButton(false)
        }, 600)
      }
    } else {
      // No map params in URL - just mark as processed (might be filter-only change)
      lastProcessedUrlRef.current = currentUrlParams
    }
    // Only depend on searchParams to avoid infinite loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (urlUpdateTimeoutRef.current) {
        clearTimeout(urlUpdateTimeoutRef.current)
      }
    }
  }, [])

  return (
    <MapViewContainer>
      <MainMap>
        <MapContainer
          center={mapCenter}
          zoom={mapZoom}
          style={{ height: "100%", width: "100%" }}
          zoomControl={true}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />

          <MapViewUpdater
            center={mapCenter}
            zoom={mapZoom}
            isUpdatingFromUrl={isUpdatingFromUrlRef}
          />

          <MapInstanceCapture mapRef={mapRef} />

          <MapEventHandler
            onBoundsChange={handleBoundsChange}
            onViewChange={handleViewChange}
            isUpdatingFromUrl={isUpdatingFromUrlRef}
            onUserInteraction={handleUserInteraction}
          />

          <FilterChangeHandler
            onBoundsChange={handleBoundsChange}
            filters={{
              mode: state.filters.mode,
              minConfidence: state.filters.minConfidence,
              sortBy: state.filters.sortBy,
              sourceFilter: state.filters.sourceFilter,
            }}
          />

          {/* Render individual benches */}
          {mapData.benches?.map((bench) => {
            const isSelected = bench.id === selectedBenchId
            const isHovered = bench.id === hoveredBenchId
            const markerColor = isSelected
              ? "#ef4444"
              : isHovered
                ? "#f59e0b"
                : "#3b82f6"
            const markerSize = isSelected || isHovered ? 32 : 24
            const iconSizeValue = isSelected || isHovered ? 36 : 28
            const anchorValue = isSelected || isHovered ? 18 : 14
            const markerIconSize: [number, number] = [
              iconSizeValue,
              iconSizeValue,
            ]
            const markerAnchor: [number, number] = [anchorValue, anchorValue]

            return (
              <Marker
                key={bench.id}
                position={[bench.lat, bench.lng]}
                icon={divIcon({
                  className: "custom-bench-marker",
                  html: `<div style="
                  width: ${markerSize}px;
                  height: ${markerSize}px;
                  background: ${markerColor};
                  border: 2px solid white;
                  border-radius: 50%;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  color: white;
                  font-size: ${isSelected || isHovered ? "14px" : "10px"};
                  font-weight: bold;
                  cursor: pointer;
                  box-shadow: 0 2px 6px rgba(0,0,0,0.4);
                  transition: all 0.2s ease;
                ">🪑</div>`,
                  iconSize: markerIconSize,
                  iconAnchor: markerAnchor,
                })}
                eventHandlers={{
                  click: () => handleBenchClick(bench.id),
                }}
              >
                <Popup>
                  <div style={{ minWidth: "200px" }}>
                    <h4>
                      <PopupTitleLink to={`/bench/${bench.id}`}>
                        Bench #{bench.id}
                      </PopupTitleLink>
                    </h4>
                    <p>
                      <strong>Confidence:</strong>{" "}
                      {(bench.best_confidence * 100).toFixed(1)}%
                    </p>
                    <p>
                      <strong>Distance:</strong>{" "}
                      {bench.distance_km < 1
                        ? `${bench.distance_meters}m`
                        : `${bench.distance_km}km`}
                    </p>
                    <p>
                      <strong>Images:</strong> {bench.image_count}
                    </p>
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>

        {loading && (
          <MapLoadingOverlay>
            <LoadingContent>
              <LoadingSpinner size="large" />
              <LoadingText>Searching for benches...</LoadingText>
            </LoadingContent>
          </MapLoadingOverlay>
        )}

        {showSearchButton && (
          <SearchButton onClick={handleSearchHere} type="button">
            🔍 Search Here
          </SearchButton>
        )}
      </MainMap>

      <MapSidebar>
        <SidebarHeader>
          <h3>Nearby Benches</h3>
          <SidebarStats>
            {loading
              ? "Searching..."
              : `${mapData.benches?.length || 0} benches in view`}
          </SidebarStats>
        </SidebarHeader>

        <SidebarContent>
          {loading && (
            <SidebarLoading>
              <LoadingSpinner />
              <p>Searching for benches...</p>
            </SidebarLoading>
          )}

          {!loading && mapData.totalCount === 0 && (
            <SidebarPlaceholder>
              <div className="icon">🗺️</div>
              <p>No benches found in this area</p>
              <small>Try zooming out or adjusting your filters</small>
            </SidebarPlaceholder>
          )}

          {/* Render individual benches */}
          {!loading && mapData.benches && mapData.benches.length > 0 && (
            <div>
              {mapData.benches.map((bench) => {
                const imageUrl = bench.image_filenames?.[0]
                  ? `/images/${bench.image_filenames[0]}`
                  : null

                return (
                  <MapBenchCard
                    key={bench.id}
                    $selected={selectedBenchId === bench.id}
                    $hovered={hoveredBenchId === bench.id}
                    onClick={() => handleBenchClick(bench.id)}
                    onMouseEnter={() => setHoveredBenchId(bench.id)}
                    onMouseLeave={() => setHoveredBenchId(null)}
                  >
                    <MapCardImage>
                      {imageUrl ? (
                        <img
                          src={imageUrl}
                          alt={`Bench ${bench.id}`}
                          loading="lazy"
                        />
                      ) : (
                        <div className="placeholder">🪑</div>
                      )}
                    </MapCardImage>
                    <MapCardContent>
                      <MapCardHeader>
                        <MapCardTitle>
                          <MapCardTitleLink to={`/bench/${bench.id}`}>
                            Bench #{bench.id}
                          </MapCardTitleLink>
                        </MapCardTitle>
                        <MapCardConfidence $show={state.debugMode}>
                          {(bench.best_confidence * 100).toFixed(0)}%
                        </MapCardConfidence>
                      </MapCardHeader>
                      <MapCardMeta>
                        <span>
                          📍{" "}
                          {bench.distance_km < 1
                            ? `${bench.distance_meters}m`
                            : `${bench.distance_km}km`}
                        </span>
                      </MapCardMeta>
                    </MapCardContent>
                  </MapBenchCard>
                )
              })}
            </div>
          )}
        </SidebarContent>
      </MapSidebar>

      {/* Modal for bench details */}
      <Modal
        isOpen={modalOpen}
        onClose={handleModalClose}
        bench={selectedBench}
        imageUrl={selectedImageUrl}
        imageId={selectedImageId}
        allBenches={mapData.benches}
        currentIndex={currentModalIndex}
        onNavigate={handleModalNavigate}
        onReport={() => setIsReportModalOpen(true)}
        onImageSelect={handleImageSelect}
      />

      {/* Report Modal */}
      {selectedBench && (
        <ReportModal
          bench={selectedBench}
          imageUrl={selectedImageUrl || undefined}
          imageId={selectedImageId || undefined}
          isOpen={isReportModalOpen}
          onClose={() => setIsReportModalOpen(false)}
        />
      )}
    </MapViewContainer>
  )
}

export default MapView
