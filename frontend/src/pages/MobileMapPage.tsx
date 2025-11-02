import { divIcon } from "leaflet"
import type React from "react"
import { useCallback, useEffect, useState } from "react"
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet"
import styled from "styled-components"
import "leaflet/dist/leaflet.css"
import "../utils/leafletFix"
import LoadingSpinner from "../components/LoadingSpinner/LoadingSpinner"
import { useApp } from "../contexts/AppContext"
import { getCurrentLocation } from "../utils/imageCapture"

const PageContainer = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
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
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  padding: ${({ theme }) => theme.spacing[4]};
  box-shadow: ${({ theme }) => theme.shadows.xl};
  z-index: 1002;
  transform: ${({ $swipeOffset = 0 }) => `translateX(${$swipeOffset}px)`};
  transition: ${({ $swiping }) => ($swiping ? "none" : "transform 0.3s ease-out")};
  touch-action: pan-y;
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

const MobileMapPage: React.FC = () => {
  const { state, loadMoreBenches, setUserLocation } = useApp()
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

  // Sort benches by distance (they should already be sorted, but ensure it)
  const sortedBenches = [...(state.benches || [])].sort((a, b) => {
    return (a.distance_meters || 0) - (b.distance_meters || 0)
  })

  const currentBench = sortedBenches[currentBenchIndex] || null

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
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />

          <MapCenterUpdater center={mapCenter} zoom={16} />

          {/* User location marker */}
          <Marker
            position={[userLocation.lat, userLocation.lng]}
            icon={divIcon({
              html: "📍",
              className: "user-location-marker",
              iconSize: [32, 32],
              iconAnchor: [16, 32],
            })}
          />

          {/* Bench markers */}
          {sortedBenches.map((bench, index) => {
            const isCurrent = index === currentBenchIndex
            return (
              <Marker
                key={bench.id}
                position={[bench.lat, bench.lng]}
                icon={divIcon({
                  html: isCurrent ? "🪑" : "🪑",
                  className: `bench-marker ${isCurrent ? "current" : ""}`,
                  iconSize: isCurrent ? [40, 40] : [30, 30],
                  iconAnchor: isCurrent ? [20, 40] : [15, 30],
                })}
                zIndexOffset={isCurrent ? 1000 : 0}
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

      {/* Bench info card */}
      {currentBench && userLocation && (
        <BenchCard
          $swiping={swipeStartX !== null}
          $swipeOffset={swipeOffset}
          onTouchStart={handleCardTouchStart}
          onTouchMove={handleCardTouchMove}
          onTouchEnd={handleCardTouchEnd}
        >
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
        </BenchCard>
      )}
    </PageContainer>
  )
}

export default MobileMapPage
