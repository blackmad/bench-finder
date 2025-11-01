import type React from "react"
import { useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import styled from "styled-components"
import Header from "../components/Header/Header"
import MapView from "../components/MapView/MapView"
import { useApp } from "../contexts/AppContext"
import { searchParamsToFilters, updateUrlWithFilters } from "../utils/urlParams"

const PageContainer = styled.div`
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Prevent page scrolling */
`

const ViewContainer = styled.div`
  flex: 1;
  width: 100%;
  min-height: 0; /* Important for flex children to respect parent height */
  overflow: hidden; /* Prevent scrolling at this level */
  display: flex;
  flex-direction: column;
`

const MapPage: React.FC = () => {
  const { state, updateFilters } = useApp()
  const [searchParams, setSearchParams] = useSearchParams()

  // Initialize filters from URL on mount (only once when config is ready)
  useEffect(() => {
    if (state.config) {
      const urlFilters = searchParamsToFilters(searchParams, state.filters)
      const hasChanges = Object.keys(urlFilters).some((key) => {
        const filterKey = key as keyof typeof urlFilters
        return state.filters[filterKey] !== urlFilters[filterKey]
      })

      if (hasChanges) {
        updateFilters(urlFilters)
      }
    }
    // Only run when config or searchParams change, not when filters change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.config, searchParams, state.filters, updateFilters])

  // Update URL when filters change (but not map view params - those are handled by MapView)
  useEffect(() => {
    if (state.config) {
      // Preserve map view params (lat, lng, zoom) - MapView manages these exclusively
      updateUrlWithFilters(state.filters, setSearchParams, [
        "lat",
        "lng",
        "zoom",
      ])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    state.config,
    state.filters.minConfidence,
    state.filters.sourceFilter,
    state.filters.sortBy,
    state.filters.mode,
    state.filters.includeDetectionData,
    setSearchParams,
    state.filters,
    // Don't include startLat/startLng as those are managed by MapView
  ])

  return (
    <PageContainer>
      <Header />
      <ViewContainer>
        <MapView />
      </ViewContainer>
    </PageContainer>
  )
}

export default MapPage
