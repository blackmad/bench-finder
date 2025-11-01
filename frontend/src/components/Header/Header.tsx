import { Grid, MapIcon, Navigation2, Settings, Shuffle, Plus } from "lucide-react"
import type React from "react"
import { useCallback, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import styled from "styled-components"
import { useApp } from "../../contexts/AppContext"
import { buildUrlWithFilters } from "../../utils/urlParams"
import { DataSource, BenchMode } from "../../api"

const HeaderContainer = styled.header`
  background: ${({ theme }) => theme.glass.background};
  backdrop-filter: ${({ theme }) => theme.glass.backdrop};
  border-bottom: ${({ theme }) => theme.glass.border};
  box-shadow: ${({ theme }) => theme.glass.shadow};
  position: sticky;
  top: 0;
  z-index: ${({ theme }) => theme.zIndex.sticky};
  padding: ${({ theme }) => theme.spacing[3]} 0;
`

const HeaderContent = styled.div`
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 ${({ theme }) => theme.spacing[5]};
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing[4]};
`

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[4]};
`

const Title = styled.h1`
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  font-family: ${({ theme }) => theme.typography.fonts.display || theme.typography.fonts.primary};
  margin: 0;
  letter-spacing: ${({ theme }) => theme.typography.letterSpacing.tight};
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
`

const TitleIcon = styled.span`
  font-size: 1.2em;
  line-height: 1;
`

const ViewToggle = styled.div`
  display: flex;
  background: ${({ theme }) => theme.colors.gray100};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  padding: ${({ theme }) => theme.spacing[1]};
  gap: ${({ theme }) => theme.spacing[1]};
  box-shadow: ${({ theme }) => theme.shadows.inner};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
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
  border-radius: ${({ theme }) => theme.borderRadius.lg};
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
  position: relative;

  &:hover {
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ $active, theme }) =>
    $active ? theme.colors.background : theme.colors.gray200};
    transform: translateY(-1px);
  }

  &:active {
    transform: scale(0.98) translateY(0);
  }

  svg {
    width: 18px;
    height: 18px;
    opacity: ${({ $active }) => ($active ? 1 : 0.7)};
    transition: opacity ${({ theme }) => theme.transitions.fast};
  }

  @media (max-width: ${({ theme }) => theme.breakpoints.sm}) {
    .label {
      display: none;
    }
  }
`

const Controls = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[3]};
  flex-wrap: wrap;
  align-items: flex-end;
`

const ControlGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[1]};
  justify-content: flex-end;

  label {
    line-height: 1.2;
    height: 16px;
    display: flex;
    align-items: center;
  }
`

const ControlLabel = styled.label`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: ${({ theme }) => theme.spacing[0]};
  line-height: 1.2;
`

const Select = styled.select`
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[3]};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  min-width: 140px;
  height: 32px;
  box-shadow: ${({ theme }) => theme.shadows.sm};

  &:hover {
    border-color: ${({ theme }) => theme.colors.gray300};
    background: ${({ theme }) => theme.colors.gray50};
    box-shadow: ${({ theme }) => theme.shadows.base};
  }

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}1a, ${({ theme }) => theme.shadows.sm};
    background: ${({ theme }) => theme.colors.background};
  }
`

const Input = styled.input`
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[3]};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.mono};
  width: 120px;
  height: 32px;
  transition: all ${({ theme }) => theme.transitions.fast};
  box-shadow: ${({ theme }) => theme.shadows.sm};

  &::placeholder {
    color: ${({ theme }) => theme.colors.textTertiary};
    font-family: ${({ theme }) => theme.typography.fonts.primary};
  }

  &:hover {
    border-color: ${({ theme }) => theme.colors.gray300};
    background: ${({ theme }) => theme.colors.gray50};
    box-shadow: ${({ theme }) => theme.shadows.base};
  }

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}1a, ${({ theme }) => theme.shadows.sm};
    background: ${({ theme }) => theme.colors.background};
  }
`

const ActionButton = styled.button<{ $variant?: "primary" | "secondary" }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[4]};
  border: ${({ $variant, theme }) =>
    $variant === "primary" ? "none" : `1px solid ${theme.colors.border}`};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  background: ${({ $variant, theme }) =>
    $variant === "primary"
      ? `linear-gradient(135deg, ${theme.colors.primary} 0%, ${theme.colors.primaryDark} 100%)`
      : theme.colors.background};
  color: ${({ $variant, theme }) =>
    $variant === "primary" ? "#ffffff" : theme.colors.textSecondary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  box-shadow: ${({ $variant, theme }) =>
    $variant === "primary" ? theme.shadows.primary : theme.shadows.sm};
  position: relative;
  overflow: hidden;
  height: 32px;
  margin-top: 16px; /* Match label height + gap to align with inputs */

  &::before {
    content: "";
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: ${({ $variant }) =>
    $variant === "primary"
      ? "rgba(255, 255, 255, 0.15)"
      : "rgba(0, 0, 0, 0.03)"};
    transition: left ${({ theme }) => theme.transitions.normal};
  }

  &:hover {
    background: ${({ $variant, theme }) =>
    $variant === "primary"
      ? `linear-gradient(135deg, ${theme.colors.primaryDark} 0%, ${theme.colors.primaryDark} 100%)`
      : theme.colors.gray50};
    border-color: ${({ $variant, theme }) =>
    $variant === "primary" ? "transparent" : theme.colors.gray300};
    box-shadow: ${({ $variant, theme }) =>
    $variant === "primary"
      ? theme.shadows.primaryHover
      : theme.shadows.base};
    transform: translateY(-1px);

    &::before {
      left: 100%;
    }
  }

  &:active {
    transform: translateY(0) scale(0.98);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;

    &:hover {
      transform: none;
    }
  }

  svg {
    width: 16px;
    height: 16px;
    position: relative;
    z-index: 1;
  }

  .label {
    position: relative;
    z-index: 1;
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

const DebugButton = styled(ActionButton) <DebugButtonProps>`
  background: ${({ $active, theme }) =>
    $active ? theme.colors.warning : theme.colors.background};
  color: ${({ $active, theme }) =>
    $active ? "#ffffff" : theme.colors.textSecondary};
  border: 1px solid ${({ $active, theme }) =>
    $active ? theme.colors.warning : theme.colors.border};
  box-shadow: ${({ $active, theme }) =>
    $active ? theme.shadows.md : theme.shadows.sm};

  &:hover {
    background: ${({ $active, theme }) =>
    $active ? theme.colors.warningLight : theme.colors.gray50};
    border-color: ${({ $active, theme }) =>
    $active ? theme.colors.warningLight : theme.colors.gray300};
    box-shadow: ${({ $active, theme }) =>
    $active ? theme.shadows.lg : theme.shadows.base};
  }
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
    // Update filters and immediately reload with the new value
    updateFilters({ [field]: value })
    // Pass the updated filter value so reload uses it immediately
    await resetAndReload({ [field]: value } as Partial<typeof state.filters>)
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

      const lat = position.coords.latitude
      const lng = position.coords.longitude

      setUserLocation(lat, lng)

      // If in map view, navigate to the new location to trigger map update
      if (currentViewMode === "map") {
        const updatedFilters = {
          ...state.filters,
          startLat: lat,
          startLng: lng,
        }
        // Include zoom in URL (default to 16 for a closer view of the area)
        const filterParams = buildUrlWithFilters(updatedFilters, "/map", ["zoom"]).split("?")[1] || ""
        const existingParams = new URLSearchParams(filterParams)
        // Set to 16 for new location (higher zoom level)
        existingParams.set("zoom", "16")
        const url = `/map?${existingParams.toString()}`
        navigate(url)
      } else {
        // In cards view, just reload the benches
        await resetAndReload()
      }
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
  }, [setUserLocation, resetAndReload, currentViewMode, state.filters, navigate])

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

  return (
    <HeaderContainer>
      <HeaderContent>
        <HeaderLeft>
          <Title>
            <TitleIcon>🪑</TitleIcon>
            Bench Finder
          </Title>
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
                    handleFilterChange("sourceFilter", e.target.value === "all" ? "all" : e.target.value as DataSource)
                  }
                >
                  <option value={DataSource.OSM}>OSM + StreetView</option>
                  <option value={DataSource.MAPILLARY}>Mapillary</option>
                  <option value="all">All Sources</option>
                </Select>
              </ControlGroup>
              <ControlGroup>
                <ControlLabel>Bench Mode</ControlLabel>
                <Select
                  value={state.filters.mode}
                  onChange={(e) => {
                    const selectedMode = e.target.value as BenchMode
                    handleFilterChange("mode", selectedMode)
                  }}
                >
                  <option value={BenchMode.BENCHES}>🪑 Detected Benches</option>
                  <option value={BenchMode.NO_BENCH}>❌ No Bench Found</option>
                  <option value={BenchMode.BOTH}>🔄 Both Types</option>
                </Select>
              </ControlGroup>
              <ControlGroup>
                <ControlLabel>Detection Data</ControlLabel>
                <Select
                  value={state.filters.includeDetectionData ? "yes" : "no"}
                  onChange={(e) =>
                    handleFilterChange("includeDetectionData", e.target.value === "yes")
                  }
                >
                  <option value="no">Basic Info Only</option>
                  <option value="yes">Include Detection Data</option>
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
            <Navigation2 />
            <span className="label">
              {locationLoading ? "Locating..." : "My Location"}
            </span>
          </ActionButton>

          <ActionButton
            $variant="secondary"
            onClick={() => navigate("/report-missing-bench")}
            title="Report a bench that's missing from our database"
          >
            <Plus />
            <span className="label">Report Missing</span>
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
      </HeaderContent>
    </HeaderContainer>
  )
}

export default Header
