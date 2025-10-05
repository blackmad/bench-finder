import type React from "react"
import { useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import styled from "styled-components"
import Header from "../components/Header/Header"
import MapView from "../components/MapView/MapView"
import { useApp } from "../contexts/AppContext"
import { searchParamsToFilters, updateUrlWithFilters } from "../utils/urlParams"

const PageContainer = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
`

const ViewContainer = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  width: 100%;
  height: calc(100vh - 140px);
  min-height: calc(100vh - 140px);
`

const MapPage: React.FC = () => {
  const { state, updateFilters } = useApp()
  const [searchParams, _setSearchParams] = useSearchParams()

  // Initialize filters from URL on mount
  useEffect(() => {
    if (state.config) {
      const urlFilters = searchParamsToFilters(searchParams, state.filters)
      if (Object.keys(urlFilters).length > 0) {
        updateFilters(urlFilters)
      }
    }
  }, [state.config, searchParams, updateFilters, state.filters])

  // Update URL when filters change
  useEffect(() => {
    if (state.config) {
      updateUrlWithFilters(state.filters, "/map")
    }
  }, [state.filters, state.config])

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
