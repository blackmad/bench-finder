import { Grid, MapIcon, MapPin, Settings, Shuffle, Plus } from "lucide-react"
import type React from "react"
import { useCallback, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import styled from "styled-components"
import { useApp } from "../../contexts/AppContext"
import { buildUrlWithFilters } from "../../utils/urlParams"
import { DataSource, BenchMode } from "../../api"

const HeaderContainer = styled.header`
  background: ${({ theme }) => theme.colors.background};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: ${({ theme }) => theme.shadows.base};
  position: sticky;
  top: 0;
  z-index: ${({ theme }) => theme.zIndex.sticky};
  padding: ${({ theme }) => theme.spacing[6]} 0;
  backdrop-filter: blur(8px);
  background: rgba(255, 255, 255, 0.95);
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
  gap: ${({ theme }) => theme.spacing[6]};
`

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[8]};
`

const Title = styled.h1`
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  margin: 0;
  letter-spacing: -0.025em;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[3]};
`

const TitleIcon = styled.span`
  font-size: 1.2em;
  line-height: 1;
`

const ViewToggle = styled.div`
  display: flex;
  background: ${({ theme }) => theme.colors.gray100};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[1]};
  gap: ${({ theme }) => theme.spacing[1]};
  box-shadow: ${({ theme }) => theme.shadows.inner};
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
  border-radius: ${({ theme }) => theme.borderRadius.md};
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
  }

  &:active {
    transform: scale(0.98);
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
  gap: ${({ theme }) => theme.spacing[4]};
  flex-wrap: wrap;
  align-items: flex-end;
`

const ControlGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[1]};
`

const ControlLabel = styled.label`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: ${({ theme }) => theme.spacing[1]};
`

const Select = styled.select`
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
  border: 1.5px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  min-width: 140px;

  &:hover {
    border-color: ${({ theme }) => theme.colors.gray300};
    background: ${({ theme }) => theme.colors.gray50};
  }

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}1a;
    background: ${({ theme }) => theme.colors.background};
  }
`

const Input = styled.input`
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
  border: 1.5px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.mono};
  width: 120px;
  transition: all ${({ theme }) => theme.transitions.fast};

  &::placeholder {
    color: ${({ theme }) => theme.colors.textTertiary};
    font-family: ${({ theme }) => theme.typography.fonts.primary};
  }

  &:hover {
    border-color: ${({ theme }) => theme.colors.gray300};
    background: ${({ theme }) => theme.colors.gray50};
  }

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}1a;
    background: ${({ theme }) => theme.colors.background};
  }
`

const ActionButton = styled.button<{ $variant?: "primary" | "secondary" }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
  border: 1.5px solid ${({ $variant, theme }) =>
    $variant === "primary" ? theme.colors.primary : theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ $variant, theme }) =>
    $variant === "primary" ? theme.colors.primary : theme.colors.background};
  color: ${({ $variant, theme }) =>
    $variant === "primary" ? "#ffffff" : theme.colors.textSecondary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: ${({ theme }) => theme.typography.fonts.primary};
  box-shadow: ${({ $variant, theme }) =>
    $variant === "primary" ? `0 2px 4px ${theme.colors.primary}25` : theme.shadows.sm};
  position: relative;
  overflow: hidden;

  &::before {
    content: "";
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: ${({ $variant }) =>
    $variant === "primary"
      ? "rgba(255, 255, 255, 0.1)"
      : "rgba(0, 0, 0, 0.03)"};
    transition: left ${({ theme }) => theme.transitions.normal};
  }

  &:hover {
    background: ${({ $variant, theme }) =>
    $variant === "primary" ? theme.colors.primaryDark : theme.colors.gray50};
    border-color: ${({ $variant, theme }) =>
    $variant === "primary" ? theme.colors.primaryDark : theme.colors.gray300};
    box-shadow: ${({ $variant, theme }) =>
    $variant === "primary"
      ? `0 4px 8px ${theme.colors.primary}35`
      : theme.shadows.md};
    transform: translateY(-1px);

    &::before {
      left: 100%;
    }
  }

  &:active {
    transform: translateY(0);
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
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
  background: ${({ theme }) => theme.colors.gray50};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
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
  const modeText = ""
  const statsText =
    currentViewMode === "cards"
      ? `Showing ${totalShown} high-confidence benches${modeText}`
      : `${totalShown} benches in view`

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
                    handleFilterChange("sourceFilter", e.target.value === "all" ? "all" : e.target.value as DataSource)
                  }
                >
                  <option value="all">All Sources</option>
                  <option value={DataSource.OSM}>OSM + StreetView</option>
                  <option value={DataSource.MAPILLARY}>Mapillary</option>
                </Select>
              </ControlGroup>
              <ControlGroup>
                <ControlLabel>Bench Mode</ControlLabel>
                <Select
                  value={state.filters.mode}
                  onChange={(e) =>
                    handleFilterChange("mode", e.target.value as BenchMode)
                  }
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
            <MapPin />
            <span className="label">
              {locationLoading ? "Locating..." : "Current Location"}
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

        <Stats>{statsText}</Stats>
      </HeaderContent>
    </HeaderContainer>
  )
}

export default Header
