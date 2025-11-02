import { divIcon, type LatLngBounds } from "leaflet"
import type React from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import {
    MapContainer,
    Marker,
    TileLayer,
    useMap,
    useMapEvents,
} from "react-leaflet"
import styled from "styled-components"
import "leaflet/dist/leaflet.css"
import "../utils/leafletFix"
import type { WebBenchData } from "../api"
import LoadingSpinner from "../components/LoadingSpinner/LoadingSpinner"
import Modal from "../components/Modal/Modal"
import { useApp } from "../contexts/AppContext"
import { benchApi } from "../services/api"
import { getCurrentLocation } from "../utils/imageCapture"

const PageContainer = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  height: 100dvh; /* Use dynamic viewport height for mobile */
  overflow: hidden;
  z-index: 1000;
  background: #e0e0e0;

  .leaflet-container {
    height: 100% !important;
    width: 100% !important;
    z-index: 1;
  }
`

const LoadingOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 1001;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing[4]};
  color: white;
`

const LoadingText = styled.div`
  font-size: ${({ theme }) => theme.typography.sizes.base};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  text-align: center;
  padding: 0 ${({ theme }) => theme.spacing[4]};
`

const LocationPrompt = styled.div`
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  padding: ${({ theme }) => theme.spacing[6]};
  margin: ${({ theme }) => theme.spacing[4]};
  box-shadow: ${({ theme }) => theme.shadows.xl};
  text-align: center;
`

const LocationPromptTitle = styled.h2`
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  margin: 0 0 ${({ theme }) => theme.spacing[3]} 0;
  color: ${({ theme }) => theme.colors.textPrimary};
`

const LocationPromptText = styled.p`
  font-size: ${({ theme }) => theme.typography.sizes.base};
  color: ${({ theme }) => theme.colors.textSecondary};
  margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
`

const LocationPromptButton = styled.button`
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[6]};
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  font-size: ${({ theme }) => theme.typography.sizes.base};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  cursor: pointer;
  transition: background ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme }) => theme.colors.primaryDark};
  }

  &:active {
    transform: scale(0.98);
  }
`

const BenchCard = styled.div<{ $swiping?: boolean; $swipeOffset?: number }>`
  position: absolute;
  bottom: ${({ theme }) => theme.spacing[4]};
  left: ${({ theme }) => theme.spacing[4]};
  right: ${({ theme }) => theme.spacing[4]};
  max-height: 25vh;
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  overflow-y: auto;
  overflow-x: hidden;
  box-shadow: ${({ theme }) => theme.shadows.xl};
  z-index: 1002;
  transform: ${({ $swipeOffset = 0 }) => `translateX(${$swipeOffset}px)`};
  transition: ${({ $swiping }) => ($swiping ? "none" : "transform 0.3s ease-out")};
  touch-action: pan-y;
  display: flex;
  flex-direction: column;
  -webkit-overflow-scrolling: touch;
`

const BenchImage = styled.img`
  width: 100%;
  height: 200px;
  object-fit: cover;
  background: ${({ theme }) => theme.colors.gray100};
  flex-shrink: 0;
`

const BenchImagePlaceholder = styled.div`
  width: 100%;
  height: 200px;
  background: ${({ theme }) => theme.colors.gray100};
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: ${({ theme }) => theme.typography.sizes["4xl"]};
  color: ${({ theme }) => theme.colors.gray400};
  flex-shrink: 0;
`

const BenchCardContent = styled.div`
  padding: ${({ theme }) => theme.spacing[4]};
  padding-bottom: max(${({ theme }) => theme.spacing[6]}, calc(${({ theme }) => theme.spacing[4]} + env(safe-area-inset-bottom, 0px)));
  flex-shrink: 0;
`

const BenchCardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: ${({ theme }) => theme.spacing[2]};
`

const BenchTitle = styled.h3`
  font-size: ${({ theme }) => theme.typography.sizes.lg};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin: 0;
`

const BenchDistance = styled.div`
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[3]};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  white-space: nowrap;
`

const BenchAddress = styled.div`
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-top: ${({ theme }) => theme.spacing[2]};
  line-height: ${({ theme }) => theme.typography.lineHeights.relaxed};
`

const SwipeIndicator = styled.div<{ $direction: "left" | "right" | null }>`
  position: absolute;
  top: 50%;
  ${({ $direction }) => ($direction === "left" ? "left" : "right")}: ${({
    theme,
}) => theme.spacing[4]};
  transform: translateY(-50%);
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  border-radius: ${({ theme }) => theme.borderRadius.full};
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  z-index: 1003;
  opacity: ${({ $direction }) => ($direction ? 1 : 0)};
  transition: opacity ${({ theme }) => theme.transitions.fast};
  pointer-events: none;
`

const NavigationControls = styled.div`
  position: absolute;
  bottom: calc(
    ${({ theme }) => theme.spacing[24] || "192px"} + env(safe-area-inset-bottom, 0px)
  );
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: ${({ theme }) => theme.spacing[2]};
  z-index: 1003;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[2]};
  box-shadow: ${({ theme }) => theme.shadows.xl};

  @media (max-width: 768px) {
    display: none; // Hide on mobile, use swipe instead
  }
`

const NavButton = styled.button<{ $disabled?: boolean }>`
  width: 44px;
  height: 44px;
  border: none;
  border-radius: ${({ theme }) => theme.borderRadius.md};
  background: ${({ theme, $disabled }) =>
        $disabled ? theme.colors.gray200 : theme.colors.primary};
  color: ${({ theme, $disabled }) =>
        $disabled ? theme.colors.gray400 : "white"};
  font-size: ${({ theme }) => theme.typography.sizes.lg};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  cursor: ${({ $disabled }) => ($disabled ? "not-allowed" : "pointer")};
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all ${({ theme }) => theme.transitions.fast};

  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.primaryDark};
    transform: scale(1.05);
  }

  &:active:not(:disabled) {
    transform: scale(0.95);
  }

  &:disabled {
    opacity: 0.5;
  }
`

const MapCenterUpdater: React.FC<{
    center: [number, number]
    zoom: number
}> = ({ center, zoom }) => {
    const map = useMap()

    useEffect(() => {
        map.setView(center, zoom, { animate: true, duration: 0.5 })
    }, [map, center, zoom])

    return null
}

// Component to detect map panning and load benches in chunks
const MapPanDetector: React.FC<{
    onBoundsChange: (bounds: LatLngBounds) => void
    userLocation: { lat: number; lng: number } | null
}> = ({ onBoundsChange }) => {
    const map = useMap()
    const lastBoundsRef = useRef<LatLngBounds | null>(null)
    const panTimeoutRef = useRef<NodeJS.Timeout | null>(null)

    useMapEvents({
        moveend: () => {
            // Debounce the bounds change
            if (panTimeoutRef.current) {
                clearTimeout(panTimeoutRef.current)
            }

            panTimeoutRef.current = setTimeout(() => {
                const bounds = map.getBounds()
                if (bounds && bounds.isValid()) {
                    // Only trigger if bounds have changed significantly (more than ~10% in any direction)
                    if (lastBoundsRef.current) {
                        const lastBounds = lastBoundsRef.current
                        const latDiff =
                            Math.abs(bounds.getNorth() - lastBounds.getNorth()) +
                            Math.abs(bounds.getSouth() - lastBounds.getSouth())
                        const lngDiff =
                            Math.abs(bounds.getEast() - lastBounds.getEast()) +
                            Math.abs(bounds.getWest() - lastBounds.getWest())

                        const latRange = Math.abs(bounds.getNorth() - bounds.getSouth())
                        const lngRange = Math.abs(bounds.getEast() - bounds.getWest())

                        // If map moved significantly (more than 10% of current view), load new benches
                        if (latDiff > latRange * 0.1 || lngDiff > lngRange * 0.1) {
                            onBoundsChange(bounds)
                            lastBoundsRef.current = bounds
                        }
                    } else {
                        // First time, just save bounds
                        lastBoundsRef.current = bounds
                    }
                }
            }, 500) // 500ms debounce
        },
    })

    // Initialize bounds on mount
    useEffect(() => {
        const bounds = map.getBounds()
        if (bounds && bounds.isValid()) {
            lastBoundsRef.current = bounds
        }
    }, [map])

    // Cleanup timeout on unmount
    useEffect(() => {
        return () => {
            if (panTimeoutRef.current) {
                clearTimeout(panTimeoutRef.current)
            }
        }
    }, [])

    return null
}

const MobileMapPage: React.FC = () => {
    const { state, loadMoreBenches, setUserLocation, dispatch } = useApp()
    const [userLocation, setUserLocationState] = useState<{
        lat: number
        lng: number
    } | null>(null)
    const [locationPermissionDenied, setLocationPermissionDenied] =
        useState(false)
    const [loadingLocation, setLoadingLocation] = useState(true)
    const [currentBenchIndex, setCurrentBenchIndex] = useState(0)
    const [swipeStartX, setSwipeStartX] = useState<number | null>(null)
    const [swipeOffset, setSwipeOffset] = useState(0)
    const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(
        null
    )
    const [modalOpen, setModalOpen] = useState(false)
    const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null)
    const [selectedImageId, setSelectedImageId] = useState<number | null>(null)
    const [loadingMoreBenches, setLoadingMoreBenches] = useState(false)
    const [isDragging, setIsDragging] = useState(false)
    const [wasDragging, setWasDragging] = useState(false) // Track if we just finished a drag
    const loadedBoundsRef = useRef<Set<string>>(new Set()) // Track loaded bounds to avoid duplicates
    const dragStartXRef = useRef<number | null>(null)
    const dragOffsetRef = useRef<number>(0)

    // Sort benches by distance (they should already be sorted, but ensure it)
    const sortedBenches = [...(state.benches || [])].sort((a, b) => {
        return (a.distance_meters || 0) - (b.distance_meters || 0)
    })

    const currentBench = sortedBenches[currentBenchIndex] || null

    // Handle bench marker click
    const handleBenchMarkerClick = useCallback(
        (benchId: number) => {
            const benchIndex = sortedBenches.findIndex((b) => b.id === benchId)
            if (benchIndex !== -1) {
                setCurrentBenchIndex(benchIndex)
            }
        },
        [sortedBenches]
    )

    // Handle card click to open details
    const handleCardClick = useCallback(() => {
        if (currentBench) {
            const imageUrl =
                currentBench.image_urls?.[0] ??
                (currentBench.image_filenames?.[0]
                    ? `/images/${currentBench.image_filenames[0]}`
                    : null)
            setSelectedImageUrl(imageUrl)
            setSelectedImageId(
                currentBench.image_urls?.[0]
                    ? null
                    : currentBench.image_filenames?.[0]
                        ? 1
                        : null
            )
            setModalOpen(true)
        }
    }, [currentBench])

    // Load benches when map bounds change significantly
    const handleBoundsChange = useCallback(
        async (bounds: LatLngBounds) => {
            if (!userLocation || loadingMoreBenches) return

            // Create a key for this bounds region (rounded to avoid duplicates)
            const boundsKey = `${Math.floor(bounds.getNorth() * 10) / 10}-${Math.floor(bounds.getSouth() * 10) / 10}-${Math.floor(bounds.getEast() * 10) / 10}-${Math.floor(bounds.getWest() * 10) / 10}`

            // Skip if we've already loaded benches for this region
            if (loadedBoundsRef.current.has(boundsKey)) {
                return
            }

            setLoadingMoreBenches(true)
            loadedBoundsRef.current.add(boundsKey)

            try {
                const response = await benchApi.getBenchesInBbox({
                    north: bounds.getNorth(),
                    south: bounds.getSouth(),
                    east: bounds.getEast(),
                    west: bounds.getWest(),
                    min_confidence: state.filters?.minConfidence || 0,
                    sort_by: "distance",
                    limit: 50,
                })

                const benches = Array.isArray(response.benches) ? response.benches : []

                // Merge new benches, avoiding duplicates
                const existingIds = new Set(state.benches.map((b) => b.id))
                const newBenches = benches.filter(
                    (b: WebBenchData) => !existingIds.has(b.id)
                )

                if (newBenches.length > 0) {
                    // Add benches to the existing list
                    dispatch({ type: "ADD_BENCHES", payload: newBenches })
                }
            } catch (error) {
                console.error("Error loading benches from map bounds:", error)
                // Remove the key so we can retry
                loadedBoundsRef.current.delete(boundsKey)
            } finally {
                setLoadingMoreBenches(false)
            }
        },
        [userLocation, loadingMoreBenches, state.filters, state.benches, dispatch]
    )

    // Navigate to previous/next bench
    const handlePreviousBench = useCallback(() => {
        setCurrentBenchIndex((prev) => Math.max(0, prev - 1))
    }, [])

    const handleNextBench = useCallback(() => {
        setCurrentBenchIndex((prev) => Math.min(sortedBenches.length - 1, prev + 1))
    }, [sortedBenches.length])

    // Keyboard navigation for desktop
    useEffect(() => {
        const handleKeyPress = (e: KeyboardEvent) => {
            if (modalOpen) return // Don't handle keyboard when modal is open

            if (e.key === "ArrowLeft") {
                e.preventDefault()
                handlePreviousBench()
            } else if (e.key === "ArrowRight") {
                e.preventDefault()
                handleNextBench()
            } else if (e.key === "Escape" && modalOpen) {
                setModalOpen(false)
            }
        }

        window.addEventListener("keydown", handleKeyPress)
        return () => {
            window.removeEventListener("keydown", handleKeyPress)
        }
    }, [handlePreviousBench, handleNextBench, modalOpen])

    // Mouse drag handling for desktop
    const handleCardMouseDown = useCallback((e: React.MouseEvent) => {
        if (e.button !== 0) return // Only handle left mouse button
        setIsDragging(true)
        dragStartXRef.current = e.clientX
        dragOffsetRef.current = 0
    }, [])

    const handleCardMouseMove = useCallback(
        (e: React.MouseEvent) => {
            if (!isDragging || dragStartXRef.current === null) return

            const diff = e.clientX - dragStartXRef.current
            dragOffsetRef.current = diff
            setSwipeOffset(diff)

            // Show swipe indicator
            if (Math.abs(diff) > 50) {
                if (diff > 0) {
                    setSwipeDirection("left") // Dragging right shows left arrow
                } else {
                    setSwipeDirection("right") // Dragging left shows right arrow
                }
            } else {
                setSwipeDirection(null)
            }
        },
        [isDragging]
    )

    const handleCardMouseUp = useCallback(() => {
        if (!isDragging) return

        const threshold = 100
        const didDrag = Math.abs(dragOffsetRef.current) > threshold

        if (didDrag) {
            if (dragOffsetRef.current > 0) {
                handlePreviousBench()
            } else {
                handleNextBench()
            }
            // Mark that we just dragged to prevent accidental click
            setWasDragging(true)
        }

        setIsDragging(false)
        dragStartXRef.current = null
        dragOffsetRef.current = 0
        setSwipeOffset(0)
        setSwipeDirection(null)
    }, [isDragging, handlePreviousBench, handleNextBench])

    // Global mouse move/up handlers for drag
    useEffect(() => {
        if (!isDragging) return

        const handleGlobalMouseMove = (e: MouseEvent) => {
            if (dragStartXRef.current === null) return
            const diff = e.clientX - dragStartXRef.current
            dragOffsetRef.current = diff
            setSwipeOffset(diff)

            if (Math.abs(diff) > 50) {
                if (diff > 0) {
                    setSwipeDirection("left")
                } else {
                    setSwipeDirection("right")
                }
            } else {
                setSwipeDirection(null)
            }
        }

        const handleGlobalMouseUp = () => {
            if (!isDragging) return

            const threshold = 100
            const didDrag = Math.abs(dragOffsetRef.current) > threshold

            if (didDrag) {
                if (dragOffsetRef.current > 0) {
                    handlePreviousBench()
                } else {
                    handleNextBench()
                }
                // Mark that we just dragged to prevent accidental click
                setWasDragging(true)
            }

            setIsDragging(false)
            dragStartXRef.current = null
            dragOffsetRef.current = 0
            setSwipeOffset(0)
            setSwipeDirection(null)
        }

        window.addEventListener("mousemove", handleGlobalMouseMove)
        window.addEventListener("mouseup", handleGlobalMouseUp)

        return () => {
            window.removeEventListener("mousemove", handleGlobalMouseMove)
            window.removeEventListener("mouseup", handleGlobalMouseUp)
        }
    }, [isDragging, handlePreviousBench, handleNextBench])

    // Request location permission on mount
    useEffect(() => {
        const requestLocation = async () => {
            if (!("geolocation" in navigator)) {
                setLocationPermissionDenied(true)
                setLoadingLocation(false)
                return
            }

            try {
                const location = await getCurrentLocation()
                setUserLocationState({ lat: location.lat, lng: location.lng })
                setUserLocation(location.lat, location.lng)
                setLoadingLocation(false)
            } catch (error) {
                console.warn("Location permission denied or failed:", error)
                setLocationPermissionDenied(true)
                setLoadingLocation(false)
            }
        }

        requestLocation()
    }, [setUserLocation])

    // Load benches when location is available
    useEffect(() => {
        if (
            userLocation &&
            state.config &&
            sortedBenches.length === 0 &&
            !state.loading
        ) {
            loadMoreBenches(false, {
                startLat: userLocation.lat,
                startLng: userLocation.lng,
                sortBy: "distance",
            })
        }
    }, [
        userLocation,
        state.config,
        state.loading,
        loadMoreBenches,
        sortedBenches.length,
    ])

    // Swipe gesture handling for bench card
    const handleCardTouchStart = useCallback((e: React.TouchEvent) => {
        if (e.touches.length === 1) {
            setSwipeStartX(e.touches[0].clientX)
            setSwipeOffset(0)
        }
    }, [])

    const handleCardTouchMove = useCallback(
        (e: React.TouchEvent) => {
            if (swipeStartX === null || e.touches.length !== 1) return

            const currentX = e.touches[0].clientX
            const diff = currentX - swipeStartX
            setSwipeOffset(diff)

            // Show swipe indicator
            if (Math.abs(diff) > 50) {
                if (diff > 0) {
                    setSwipeDirection("left") // Swiping right shows left arrow (go to previous)
                } else {
                    setSwipeDirection("right") // Swiping left shows right arrow (go to next)
                }
            } else {
                setSwipeDirection(null)
            }
        },
        [swipeStartX]
    )

    const handleCardTouchEnd = useCallback(() => {
        if (swipeStartX === null) return

        const threshold = 100 // Minimum swipe distance to trigger navigation

        if (Math.abs(swipeOffset) > threshold) {
            if (swipeOffset > 0) {
                // Swipe right - go to previous bench
                setCurrentBenchIndex((prev) => Math.max(0, prev - 1))
            } else {
                // Swipe left - go to next bench
                setCurrentBenchIndex((prev) =>
                    Math.min(sortedBenches.length - 1, prev + 1)
                )
            }
        }

        setSwipeStartX(null)
        setSwipeOffset(0)
        setSwipeDirection(null)
    }, [swipeStartX, swipeOffset, sortedBenches.length])

    const handleRequestLocation = useCallback(async () => {
        setLoadingLocation(true)
        setLocationPermissionDenied(false)

        try {
            const location = await getCurrentLocation()
            setUserLocationState({ lat: location.lat, lng: location.lng })
            setUserLocation(location.lat, location.lng)
            setLoadingLocation(false)
        } catch (error) {
            console.warn("Location permission denied:", error)
            setLocationPermissionDenied(true)
            setLoadingLocation(false)
        }
    }, [setUserLocation])

    // Map center based on current bench or user location
    const mapCenter: [number, number] = currentBench
        ? [currentBench.lat, currentBench.lng]
        : userLocation
            ? [userLocation.lat, userLocation.lng]
            : [52.3613577, 4.8666322] // Default to Amsterdam

    const showLoading =
        loadingLocation ||
        (userLocation && sortedBenches.length === 0 && state.loading)

    return (
        <PageContainer>
            {showLoading && (
                <LoadingOverlay>
                    <LoadingSpinner />
                    <LoadingText>
                        {loadingLocation
                            ? "Requesting location permission..."
                            : "Finding nearby benches..."}
                    </LoadingText>
                </LoadingOverlay>
            )}

            {locationPermissionDenied && !userLocation && (
                <LoadingOverlay>
                    <LocationPrompt>
                        <LocationPromptTitle>📍 Location Required</LocationPromptTitle>
                        <LocationPromptText>
                            We need your location to show you the nearest benches. Please
                            enable location access in your browser settings.
                        </LocationPromptText>
                        <LocationPromptButton onClick={handleRequestLocation}>
                            Allow Location Access
                        </LocationPromptButton>
                    </LocationPrompt>
                </LoadingOverlay>
            )}

            {userLocation && (
                <MapContainer
                    center={mapCenter}
                    zoom={16}
                    style={{ height: "100%", width: "100%" }}
                    zoomControl={true}
                    scrollWheelZoom={true}
                >
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                        maxZoom={19}
                    />

                    <MapCenterUpdater center={mapCenter} zoom={16} />

                    {/* Map pan detector for loading benches in chunks */}
                    <MapPanDetector
                        onBoundsChange={handleBoundsChange}
                        userLocation={userLocation}
                    />

                    {/* User location marker */}
                    <Marker
                        position={[userLocation.lat, userLocation.lng]}
                        icon={divIcon({
                            html: `
                <div style="
                  width: 32px;
                  height: 32px;
                  background: #2563eb;
                  border: 3px solid white;
                  border-radius: 50%;
                  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  font-size: 18px;
                ">📍</div>
              `,
                            className: "user-location-marker",
                            iconSize: [32, 32],
                            iconAnchor: [16, 16],
                        })}
                    />

                    {/* Bench markers */}
                    {sortedBenches.map((bench, index) => {
                        const isCurrent = index === currentBenchIndex
                        const size = isCurrent ? 56 : 40
                        const borderWidth = isCurrent ? 4 : 3
                        const shadowSize = isCurrent ? "0 4px 12px" : "0 2px 8px"
                        const bgColor = isCurrent ? "#059669" : "#10b981"

                        return (
                            <Marker
                                key={bench.id}
                                position={[bench.lat, bench.lng]}
                                icon={divIcon({
                                    html: `
                    <div style="
                      width: ${size}px;
                      height: ${size}px;
                      background: ${bgColor};
                      border: ${borderWidth}px solid white;
                      border-radius: 12px;
                      box-shadow: ${shadowSize} rgba(0,0,0,0.4);
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      font-size: ${isCurrent ? "28px" : "20px"};
                      transform: rotate(-15deg);
                      transition: all 0.3s ease;
                      cursor: pointer;
                    ">🪑</div>
                  `,
                                    className: `bench-marker ${isCurrent ? "current" : ""}`,
                                    iconSize: [size, size],
                                    iconAnchor: [size / 2, size / 2],
                                })}
                                zIndexOffset={isCurrent ? 1000 : 0}
                                eventHandlers={{
                                    click: () => {
                                        handleBenchMarkerClick(bench.id)
                                    },
                                }}
                            />
                        )
                    })}
                </MapContainer>
            )}

            {/* Swipe indicators */}
            <SwipeIndicator $direction={swipeDirection}>
                {swipeDirection === "left" && "←"}
                {swipeDirection === "right" && "→"}
            </SwipeIndicator>

            {/* Navigation controls for desktop */}
            {currentBench && sortedBenches.length > 1 && (
                <NavigationControls>
                    <NavButton
                        $disabled={currentBenchIndex === 0}
                        onClick={handlePreviousBench}
                        disabled={currentBenchIndex === 0}
                        aria-label="Previous bench"
                    >
                        ←
                    </NavButton>
                    <NavButton
                        $disabled={currentBenchIndex === sortedBenches.length - 1}
                        onClick={handleNextBench}
                        disabled={currentBenchIndex === sortedBenches.length - 1}
                        aria-label="Next bench"
                    >
                        →
                    </NavButton>
                </NavigationControls>
            )}

            {/* Bench info card */}
            {currentBench && userLocation && (
                <BenchCard
                    $swiping={swipeStartX !== null || isDragging}
                    $swipeOffset={swipeOffset}
                    onTouchStart={handleCardTouchStart}
                    onTouchMove={handleCardTouchMove}
                    onTouchEnd={handleCardTouchEnd}
                    onMouseDown={handleCardMouseDown}
                    onMouseMove={handleCardMouseMove}
                    onMouseUp={handleCardMouseUp}
                    onClick={() => {
                        // Only open modal if we didn't just drag
                        if (!isDragging && !wasDragging && Math.abs(swipeOffset) < 10) {
                            handleCardClick()
                        }
                        // Reset wasDragging after a short delay
                        if (wasDragging) {
                            setTimeout(() => setWasDragging(false), 100)
                        }
                    }}
                    style={{ cursor: "pointer" }}
                >
                    {/* Bench image */}
                    {(() => {
                        const imageUrl =
                            currentBench.image_urls?.[0] ??
                            (currentBench.image_filenames?.[0]
                                ? `/images/${currentBench.image_filenames[0]}`
                                : null)
                        return imageUrl ? (
                            <BenchImage src={imageUrl} alt={`Bench ${currentBench.id}`} />
                        ) : (
                            <BenchImagePlaceholder>🪑</BenchImagePlaceholder>
                        )
                    })()}

                    <BenchCardContent>
                        <BenchCardHeader>
                            <BenchTitle>Bench #{currentBench.id}</BenchTitle>
                            <BenchDistance>
                                {currentBench.distance_km < 1
                                    ? `${currentBench.distance_meters}m`
                                    : `${currentBench.distance_km}km`}
                            </BenchDistance>
                        </BenchCardHeader>
                        {currentBench.reverse_geocode?.formatted_address && (
                            <BenchAddress>
                                {currentBench.reverse_geocode.formatted_address}
                            </BenchAddress>
                        )}
                        <BenchAddress
                            style={{ marginTop: "8px", fontSize: "0.75rem", opacity: 0.7 }}
                        >
                            {currentBenchIndex + 1} of {sortedBenches.length} • Swipe to
                            navigate
                        </BenchAddress>
                    </BenchCardContent>
                </BenchCard>
            )}

            {/* Modal for bench details */}
            {modalOpen && currentBench && (
                <Modal
                    isOpen={modalOpen}
                    onClose={() => setModalOpen(false)}
                    bench={currentBench}
                    imageUrl={selectedImageUrl}
                    imageId={selectedImageId}
                    allBenches={sortedBenches}
                    currentIndex={currentBenchIndex}
                    onNavigate={(direction: "prev" | "next") => {
                        // Update to the next/prev bench
                        const newIndex =
                            direction === "prev"
                                ? Math.max(0, currentBenchIndex - 1)
                                : Math.min(sortedBenches.length - 1, currentBenchIndex + 1)
                        const newBench = sortedBenches[newIndex]
                        if (newBench && newIndex !== currentBenchIndex) {
                            setCurrentBenchIndex(newIndex)
                            // Update selected image for new bench
                            const imageUrl =
                                newBench.image_urls?.[0] ??
                                (newBench.image_filenames?.[0]
                                    ? `/images/${newBench.image_filenames[0]}`
                                    : null)
                            setSelectedImageUrl(imageUrl)
                            setSelectedImageId(
                                newBench.image_urls?.[0]
                                    ? null
                                    : newBench.image_filenames?.[0]
                                        ? 1
                                        : null
                            )
                        }
                    }}
                />
            )}
        </PageContainer>
    )
}

export default MobileMapPage
