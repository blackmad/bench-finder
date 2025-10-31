import { divIcon, type LatLngBounds } from "leaflet"
import type React from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet"
import { Link, useSearchParams } from "react-router-dom"
import styled from "styled-components"
import "leaflet/dist/leaflet.css"
import "../../utils/leafletFix"
import type {
  BboxBenchResponse,
  WebBenchData,
} from "../../api"
import { useApp } from "../../contexts/AppContext"
import { benchApi } from "../../services/api"
import LoadingSpinner from "../LoadingSpinner/LoadingSpinner"
import Modal from "../Modal/Modal"

const MapViewContainer = styled.div`
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  display: flex;
  background: #f0f0f0; /* Temporary debug background */
`

const MainMap = styled.div`
  flex: 1;
  height: 100%;
  min-height: 500px;
  position: relative;
  background: #e0e0e0; /* Temporary debug background */
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

const MapBenchCard = styled.div<{ $selected?: boolean }>`
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
  padding: ${({ theme }) => theme.spacing[3]};
  cursor: pointer;
  transition: background-color ${({ theme }) => theme.transitions.fast};
  display: flex;
  gap: ${({ theme }) => theme.spacing[4]};
  background: ${({ $selected, theme }) =>
    $selected ? `${theme.colors.primary}10` : "transparent"};
  border-left: ${({ $selected, theme }) =>
    $selected ? `3px solid ${theme.colors.primary}` : "3px solid transparent"};

  &:hover {
    background: ${({ theme }) => theme.colors.backgroundTertiary};
  }
`

const MapCardImage = styled.div`
  width: 120px;
  height: 80px;
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
    font-size: ${({ theme }) => theme.typography.sizes.xl};
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

const SearchControls = styled.div`
  position: absolute;
  top: ${({ theme }) => theme.spacing[5]};
  right: ${({ theme }) => theme.spacing[5]};
  z-index: 1000;
  background: ${({ theme }) => theme.colors.background};
  padding: ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  box-shadow: ${({ theme }) => theme.shadows.lg};
  max-width: 250px;

  @media (max-width: ${({ theme }) => theme.breakpoints.md}) {
    top: ${({ theme }) => theme.spacing[3]};
    right: ${({ theme }) => theme.spacing[3]};
    left: ${({ theme }) => theme.spacing[3]};
    max-width: none;
    padding: ${({ theme }) => theme.spacing[3]};
  }

  h4 {
    margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
    font-size: ${({ theme }) => theme.typography.sizes.base};
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  button {
    width: 100%;
    padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
    border: none;
    border-radius: ${({ theme }) => theme.borderRadius.base};
    background: ${({ theme }) => theme.colors.primary};
    color: white;
    cursor: pointer;
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    transition: background ${({ theme }) => theme.transitions.fast};

    &:hover {
      background: ${({ theme }) => theme.colors.primaryDark};
    }
  }
`

// Component to handle map events
const MapEventHandler: React.FC<{
  onBoundsChange: (bounds: LatLngBounds) => void
  onViewChange: (center: [number, number], zoom: number) => void
  isUpdatingFromUrl: React.MutableRefObject<boolean>
}> = ({ onBoundsChange, onViewChange, isUpdatingFromUrl }) => {
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
      const center = map.getCenter()
      const zoom = map.getZoom()
      onBoundsChangeRef.current(bounds)
      onViewChangeRef.current([center.lat, center.lng], zoom)
    }

    const handleZoomEnd = () => {
      // Skip if this is from a programmatic update
      if (isUpdatingFromUrl.current) {
        return
      }
      const center = map.getCenter()
      const zoom = map.getZoom()
      onViewChangeRef.current([center.lat, center.lng], zoom)
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
  }, [map]) // Only depend on map instance, callbacks accessed via refs

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

    // Only update if the view actually changed and it's different from what we last set
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

    if ((centerChanged || zoomChanged) && isDifferentFromLast) {
      // Set flag before updating to prevent URL updates
      isUpdatingFromUrl.current = true
      lastCenterRef.current = center
      lastZoomRef.current = zoom

      map.setView(center, zoom, { animate: false })

      // Reset flag after map has updated (events fire asynchronously)
      setTimeout(() => {
        isUpdatingFromUrl.current = false
      }, 300)
    }
  }, [map, center, zoom])

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
  const [loading, setLoading] = useState(false)
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const urlUpdateTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isUpdatingFromUrlRef = useRef(false)

  // Modal state
  const [selectedBench, setSelectedBench] = useState<WebBenchData | null>(null)
  const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null)
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [currentModalIndex, setCurrentModalIndex] = useState(0)

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
        }

        if (state.filters.sourceFilter !== "all") {
          ;(params as any).source = state.filters.sourceFilter
        }

        const response = await benchApi.getBenchesInBbox(params)

        // Handle individual bench response
        const individualResponse = response as BboxBenchResponse
        setMapData({
          benches: individualResponse.benches as WebBenchData[],
          totalCount:
            individualResponse.total_count ||
            individualResponse.benches.length,
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

  const handleSearchHere = () => {
    // This would be triggered by the search button
    // For now, it's handled automatically by map movement
  }

  const handleBenchClick = useCallback((benchId: number) => {
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
  }, [mapData.benches])

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
      newIndex = Math.max(0, Math.min(benchesForNavigation.length - 1, newIndex))

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

  const [mapCenter, setMapCenter] = useState<[number, number]>(() => getInitialCenter())
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

        // Update lat/lng (these are already used by filters, so we'll update them)
        currentParams.set("lat", center[0].toFixed(7))
        currentParams.set("lng", center[1].toFixed(7))

        // Update zoom
        currentParams.set("zoom", zoom.toString())

        const newUrlString = currentParams.toString()

        // Only update if URL actually changed
        if (newUrlString !== lastSetUrlRef.current) {
          lastSetUrlRef.current = newUrlString
          lastProcessedUrlRef.current = newUrlString
          setSearchParams(currentParams, { replace: true })
        }
      }, 200) // Reduced debounce for more responsive updates
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

    // Skip if this is the same URL we just processed
    if (currentUrlParams === lastProcessedUrlRef.current) {
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

      if (
        !Number.isNaN(lat) &&
        !Number.isNaN(lng) &&
        !Number.isNaN(zoom) &&
        (Math.abs(lat - mapCenterRef.current[0]) > 0.0001 ||
          Math.abs(lng - mapCenterRef.current[1]) > 0.0001 ||
          Math.abs(zoom - mapZoomRef.current) > 0.1)
      ) {
        // This is an external URL change - update map view
        lastProcessedUrlRef.current = currentUrlParams
        isUpdatingFromUrlRef.current = true
        setMapCenter([lat, lng])
        setMapZoom(zoom)

        // Reset flag after a delay to allow map to update
        setTimeout(() => {
          isUpdatingFromUrlRef.current = false
        }, 500)
      }
    } else if (urlLat && urlLng) {
      // URL has lat/lng but no zoom - update center only if it differs
      const lat = parseFloat(urlLat)
      const lng = parseFloat(urlLng)
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
        }, 500)
      }
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
          style={{ height: "500px", width: "100%", minHeight: "500px" }}
          zoomControl={true}
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

          <MapEventHandler
            onBoundsChange={handleBoundsChange}
            onViewChange={handleViewChange}
            isUpdatingFromUrl={isUpdatingFromUrlRef}
          />

          {/* Render individual benches */}
          {mapData.benches?.map((bench) => (
              <Marker
                key={bench.id}
                position={[bench.lat, bench.lng]}
                icon={divIcon({
                  className: "custom-bench-marker",
                  html: `<div style="
                  width: 24px;
                  height: 24px;
                  background: ${bench.id === selectedBenchId ? "#ef4444" : "#3b82f6"};
                  border: 2px solid white;
                  border-radius: 50%;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  color: white;
                  font-size: 10px;
                  font-weight: bold;
                  cursor: pointer;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">🪑</div>`,
                  iconSize: [28, 28],
                  iconAnchor: [14, 14],
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
            ))}
        </MapContainer>

        <SearchControls>
          <h4>Search This Area</h4>
          <button onClick={handleSearchHere} type="button">
            🔍 Search Here
          </button>
        </SearchControls>
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
          {!loading &&
            mapData.benches &&
            mapData.benches.length > 0 && (
              <div>
                {mapData.benches.map((bench) => {
                  const imageUrl = bench.image_filenames?.[0]
                    ? `/images/${bench.image_filenames[0]}`
                    : null

                  return (
                    <MapBenchCard
                      key={bench.id}
                      $selected={selectedBenchId === bench.id}
                      onClick={() => handleBenchClick(bench.id)}
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
      />
    </MapViewContainer>
  )
}

export default MapView
