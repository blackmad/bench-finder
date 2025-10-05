import { Grid, MapIcon, MapPin, Settings, Shuffle } from "lucide-react"
import type React from "react"
import { useCallback, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import styled from "styled-components"
import { useApp } from "../../contexts/AppContext"
import { buildUrlWithFilters } from "../../utils/urlParams"

const HeaderContainer = styled.header`
  background: ${({ theme }) => theme.colors.background};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: ${({ theme }) => theme.shadows.sm};
  position: sticky;
  top: 0;
  z-index: ${({ theme }) => theme.zIndex.sticky};
  padding: ${({ theme }) => theme.spacing[5]} 0;
`

const HeaderContent = styled.div`
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 ${({ theme }) => theme.spacing[5]};
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing[5]};
`

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[8]};
`

const Title = styled.h1`
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  margin: 0;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[3]};
`

const ViewToggle = styled.div`
  display: flex;
  background: ${({ theme }) => theme.colors.gray100};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  padding: ${({ theme }) => theme.spacing[1]};
  gap: ${({ theme }) => theme.spacing[1]};
`

interface ViewButtonProps {
  $active: boolean
}

const ViewButton = styled.button<ViewButtonProps>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
  border: none;
  border-radius: ${({ theme }) => theme.borderRadius.base};
  background: ${({ $active, theme }) =>
    $active ? theme.colors.background : "transparent"};
  color: ${({ $active, theme }) =>
    $active ? theme.colors.textPrimary : theme.colors.textSecondary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  box-shadow: ${({ $active, theme }) => ($active ? theme.shadows.sm : "none")};

  &:hover {
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ $active, theme }) =>
      $active ? theme.colors.background : theme.colors.gray200};
  }

  svg {
    width: 18px;
    height: 18px;
  }

  @media (max-width: ${({ theme }) => theme.breakpoints.sm}) {
    .label {
      display: none;
    }
  }
`

const Controls = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[4]};
  flex-wrap: wrap;
  align-items: center;
`

const ControlGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[1]};
`

const ControlLabel = styled.label`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  text-transform: uppercase;
  letter-spacing: 0.025em;
`

const Select = styled.select`
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.base};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  cursor: pointer;

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}1a;
  }
`

const Input = styled.input`
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.base};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  width: 120px;

  &::placeholder {
    color: ${({ theme }) => theme.colors.textTertiary};
  }

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}1a;
  }
`

const ActionButton = styled.button<{ $variant?: "primary" | "secondary" }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
  border: 1px solid ${({ $variant, theme }) =>
    $variant === "primary" ? theme.colors.primary : theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ $variant, theme }) =>
    $variant === "primary" ? theme.colors.primary : theme.colors.background};
  color: ${({ $variant, theme }) =>
    $variant === "primary" ? "#ffffff" : theme.colors.textSecondary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  box-shadow: ${({ $variant, theme }) =>
    $variant === "primary" ? `0 1px 3px ${theme.colors.primary}30` : "none"};

  &:hover {
    background: ${({ $variant, theme }) =>
      $variant === "primary" ? theme.colors.primaryDark : theme.colors.gray50};
    border-color: ${({ $variant, theme }) =>
      $variant === "primary" ? theme.colors.primaryDark : theme.colors.gray300};
    box-shadow: ${({ $variant, theme }) =>
      $variant === "primary"
        ? `0 2px 4px ${theme.colors.primary}40`
        : theme.shadows.sm};
  }

  &:active {
    transform: translateY(1px);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  svg {
    width: 16px;
    height: 16px;
  }

  @media (max-width: ${({ theme }) => theme.breakpoints.sm}) {
    .label {
      display: none;
    }
  }
`

interface DebugButtonProps {
  $active: boolean
}

const DebugButton = styled(ActionButton)<DebugButtonProps>`
  background: ${({ $active, theme }) =>
    $active ? theme.colors.warning : theme.colors.background};
  color: ${({ $active, theme }) =>
    $active ? "#ffffff" : theme.colors.textSecondary};
  border-color: ${({ $active, theme }) =>
    $active ? theme.colors.warning : theme.colors.border};

  &:hover {
    background: ${({ $active, theme }) =>
      $active ? theme.colors.warningLight : theme.colors.gray50};
    border-color: ${({ $active, theme }) =>
      $active ? theme.colors.warningLight : theme.colors.gray300};
  }
`

const Stats = styled.div`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
`

const CoordinatesGroup = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[3]};
  
  @media (max-width: ${({ theme }) => theme.breakpoints.md}) {
    display: none;
  }
`

export const Header: React.FC = () => {
  const {
    state,
    dispatch,
    updateFilters,
    resetAndReload,
    setUserLocation,
    feelingLucky,
  } = useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const [locationLoading, setLocationLoading] = useState(false)
  const [luckyLoading, setLuckyLoading] = useState(false)

  const currentViewMode = location.pathname === "/map" ? "map" : "cards"

  const handleViewChange = (viewMode: "cards" | "map") => {
    const targetPath = `/${viewMode}`
    const url = buildUrlWithFilters(state.filters, targetPath)
    navigate(url)
  }

  const handleLocationChange = async (
    field: "startLat" | "startLng",
    value: string
  ) => {
    const numValue = parseFloat(value)
    if (!Number.isNaN(numValue)) {
      updateFilters({ [field]: numValue })
      await resetAndReload()
    }
  }

  const handleFilterChange = async (
    field: keyof typeof state.filters,
    value: any
  ) => {
    updateFilters({ [field]: value })
    await resetAndReload()
  }

  const handleCurrentLocation = useCallback(async () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by this browser")
      return
    }

    setLocationLoading(true)

    try {
      const position = await new Promise<GeolocationPosition>(
        (resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000,
          })
        }
      )

      setUserLocation(position.coords.latitude, position.coords.longitude)
      await resetAndReload()
    } catch (error: any) {
      let message = "Unable to get location"
      switch (error.code) {
        case error.PERMISSION_DENIED:
          message = "Location access denied"
          break
        case error.POSITION_UNAVAILABLE:
          message = "Location unavailable"
          break
        case error.TIMEOUT:
          message = "Location request timeout"
          break
      }
      alert(
        `${message}. Please enter coordinates manually or allow location access.`
      )
    } finally {
      setLocationLoading(false)
    }
  }, [setUserLocation, resetAndReload])

  const handleFeelingLucky = useCallback(async () => {
    setLuckyLoading(true)
    try {
      const randomBench = await feelingLucky()
      if (randomBench) {
        // For now, just update the location to the random bench
        setUserLocation(randomBench.lat, randomBench.lng)
        if (currentViewMode === "map") {
          // In map view, we'd center on the bench
          dispatch({ type: "SET_SELECTED_BENCH", payload: randomBench.id })
        } else {
          // In cards view, we might show a modal or navigate to the bench
          await resetAndReload()
        }
      } else {
        alert(
          "No benches found matching your criteria. Try adjusting the filters."
        )
      }
    } catch (error) {
      console.error("Lucky search failed:", error)
      alert("Failed to find a random bench. Please try again.")
    } finally {
      setLuckyLoading(false)
    }
  }, [feelingLucky, setUserLocation, currentViewMode, dispatch, resetAndReload])

  const handleStartPointChange = async (value: string) => {
    if (value === "current") {
      await handleCurrentLocation()
    } else if (value !== "custom") {
      const [lat, lng] = value.split(",").map(Number)
      setUserLocation(lat, lng)
      await resetAndReload()
    }
  }
  const totalShown = state.benches?.length || 0
  const statsText =
    currentViewMode === "cards"
      ? `Showing ${totalShown} high-confidence benches`
      : `${totalShown} benches in view`

  return (
    <HeaderContainer>
      <HeaderContent>
        <HeaderLeft>
          <Title>🪑 Bench Finder</Title>
          <ViewToggle>
            <ViewButton
              $active={currentViewMode === "cards"}
              onClick={() => handleViewChange("cards")}
            >
              <Grid />
              <span className="label">Cards</span>
            </ViewButton>
            <ViewButton
              $active={currentViewMode === "map"}
              onClick={() => handleViewChange("map")}
            >
              <MapIcon />
              <span className="label">Map</span>
            </ViewButton>
          </ViewToggle>
        </HeaderLeft>

        <Controls>
          <ControlGroup>
            <ControlLabel>Starting Point</ControlLabel>
            <Select
              value="custom"
              onChange={(e) => handleStartPointChange(e.target.value)}
            >
              <option value="current">📍 Current Location</option>
              <option value="custom">Custom Location</option>
              {state.searches.map((search) => (
                <option
                  key={search.id}
                  value={`${search.start_lat},${search.start_lng}`}
                >
                  {search.query} ({search.bench_count} benches)
                </option>
              ))}
            </Select>
          </ControlGroup>

          <CoordinatesGroup>
            <ControlGroup>
              <ControlLabel>Latitude</ControlLabel>
              <Input
                type="number"
                step="0.000001"
                value={state.filters.startLat}
                onChange={(e) =>
                  handleLocationChange("startLat", e.target.value)
                }
                placeholder="52.3613577"
              />
            </ControlGroup>
            <ControlGroup>
              <ControlLabel>Longitude</ControlLabel>
              <Input
                type="number"
                step="0.000001"
                value={state.filters.startLng}
                onChange={(e) =>
                  handleLocationChange("startLng", e.target.value)
                }
                placeholder="4.8666322"
              />
            </ControlGroup>
          </CoordinatesGroup>

          {state.debugMode && (
            <>
              <ControlGroup>
                <ControlLabel>Min Confidence</ControlLabel>
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={state.filters.minConfidence}
                  onChange={(e) =>
                    handleFilterChange(
                      "minConfidence",
                      parseFloat(e.target.value)
                    )
                  }
                />
              </ControlGroup>
              <ControlGroup>
                <ControlLabel>Source</ControlLabel>
                <Select
                  value={state.filters.sourceFilter}
                  onChange={(e) =>
                    handleFilterChange("sourceFilter", e.target.value)
                  }
                >
                  <option value="all">All Sources</option>
                  <option value="osm">OSM + StreetView</option>
                  <option value="mapillary">Mapillary</option>
                </Select>
              </ControlGroup>
            </>
          )}

          <ControlGroup>
            <ControlLabel>Sort By</ControlLabel>
            <Select
              value={state.filters.sortBy}
              onChange={(e) => handleFilterChange("sortBy", e.target.value)}
            >
              <option value="distance">📍 Distance</option>
              <option value="confidence">🎯 Confidence</option>
              <option value="images">📷 Image Count</option>
              <option value="recent">🕒 Recently Added</option>
            </Select>
          </ControlGroup>

          <ActionButton
            $variant="primary"
            onClick={handleFeelingLucky}
            disabled={luckyLoading}
            title="Take me to a random bench!"
          >
            <Shuffle />
            <span className="label">
              {luckyLoading ? "Finding..." : "I'm Feeling Lucky"}
            </span>
          </ActionButton>

          <ActionButton
            onClick={handleCurrentLocation}
            disabled={locationLoading}
            title="Use my current location"
          >
            <MapPin />
            <span className="label">
              {locationLoading ? "Locating..." : "Current Location"}
            </span>
          </ActionButton>

          <DebugButton
            $active={state.debugMode}
            onClick={() => dispatch({ type: "TOGGLE_DEBUG_MODE" })}
            title={
              state.debugMode
                ? "Hide technical details"
                : "Show technical details"
            }
          >
            <Settings />
            <span className="label">Debug</span>
          </DebugButton>
        </Controls>

        <Stats>{statsText}</Stats>
      </HeaderContent>
    </HeaderContainer>
  )
}

export default Header
