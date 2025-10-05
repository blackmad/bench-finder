import React, { useCallback, useEffect } from "react"
import { useInView } from "react-intersection-observer"
import styled from "styled-components"
import BenchCard from "../components/BenchCard/BenchCard"
import Header from "../components/Header/Header"
import LoadingSpinner from "../components/LoadingSpinner/LoadingSpinner"
import MapView from "../components/MapView/MapView"
import Modal from "../components/Modal/Modal"
import { useApp } from "../contexts/AppContext"
import type { Bench } from "../types"

const PageContainer = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
`

const ViewContainer = styled.div<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "flex" : "none")};
  flex-direction: column;
  flex: 1;
  width: 100%;
  height: calc(100vh - 140px);
  min-height: calc(100vh - 140px);
`

const CardsContainer = styled.div`
  max-width: 1400px;
  margin: 0 auto;
  padding: ${({ theme }) => theme.spacing[8]} ${({ theme }) => theme.spacing[5]};
  background: ${({ theme }) => theme.colors.backgroundSecondary};
`

const BenchGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: ${({ theme }) => theme.spacing[6]};
  margin-bottom: ${({ theme }) => theme.spacing[10]};
`

const LoadingContainer = styled.div<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "flex" : "none")};
  justify-content: center;
  align-items: center;
  padding: ${({ theme }) => theme.spacing[10]};
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.base};
`

const NoResults = styled.div<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "flex" : "none")};
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing[16]} ${({ theme }) => theme.spacing[5]};
  text-align: center;
  color: ${({ theme }) => theme.colors.textSecondary};

  h3 {
    font-size: ${({ theme }) => theme.typography.sizes.xl};
    margin-bottom: ${({ theme }) => theme.spacing[2]};
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  p {
    color: ${({ theme }) => theme.colors.textSecondary};
  }

  .icon {
    font-size: ${({ theme }) => theme.typography.sizes["4xl"]};
    margin-bottom: ${({ theme }) => theme.spacing[4]};
    opacity: 0.7;
  }
`

const InfiniteScrollTrigger = styled.div`
  height: 20px;
  margin-top: ${({ theme }) => theme.spacing[5]};
`

const HomePage: React.FC = () => {
  const { state, loadMoreBenches } = useApp()
  const [selectedBench, setSelectedBench] = React.useState<Bench | null>(null)
  const [selectedImageUrl, setSelectedImageUrl] = React.useState<string | null>(
    null
  )
  const [selectedImageId, setSelectedImageId] = React.useState<number | null>(
    null
  )
  const [modalOpen, setModalOpen] = React.useState(false)

  // Intersection observer for infinite scroll
  const { ref: infiniteScrollRef, inView } = useInView({
    threshold: 0,
    rootMargin: "100px",
  })

  // Load initial data when view mode is cards
  useEffect(() => {
    if (
      state.viewMode === "cards" &&
      state.benches.length === 0 &&
      !state.loading &&
      state.config
    ) {
      loadMoreBenches()
    }
  }, [
    state.viewMode,
    state.config,
    loadMoreBenches,
    state.benches.length,
    state.loading,
  ])

  // Handle infinite scroll
  useEffect(() => {
    if (
      inView &&
      state.viewMode === "cards" &&
      state.hasMore &&
      !state.loading
    ) {
      loadMoreBenches()
    }
  }, [inView, state.viewMode, state.hasMore, state.loading, loadMoreBenches])

  // Handle filter changes - this should be handled by the context, not here
  // Removed to prevent infinite loops

  const handleImageClick = useCallback(
    (bench: Bench, imageUrl: string, imageId: number) => {
      setSelectedBench(bench)
      setSelectedImageUrl(imageUrl)
      setSelectedImageId(imageId)
      setModalOpen(true)
    },
    []
  )

  const handleStreetViewClick = useCallback((lat: number, lng: number) => {
    const url = `https://www.google.com/maps/@${lat},${lng},3a,75y,90t/data=!3m6!1e1`
    window.open(url, "_blank")
  }, [])

  const handleModalClose = useCallback(() => {
    setModalOpen(false)
    setSelectedBench(null)
    setSelectedImageUrl(null)
    setSelectedImageId(null)
  }, [])

  const showNoResults =
    state.viewMode === "cards" &&
    state.benches.length === 0 &&
    !state.loading &&
    state.currentPage > 0

  const showLoading = state.loading && state.benches.length === 0

  return (
    <PageContainer>
      <Header />

      {/* Cards View */}
      <ViewContainer $show={state.viewMode === "cards"}>
        <CardsContainer>
          <LoadingContainer $show={showLoading}>
            <LoadingSpinner />
            <span style={{ marginLeft: "12px" }}>Loading benches...</span>
          </LoadingContainer>

          <NoResults $show={showNoResults}>
            <div className="icon">🔍</div>
            <h3>No benches found</h3>
            <p>Try adjusting your search parameters or starting location.</p>
          </NoResults>

          {state.benches.length > 0 && (
            <BenchGrid>
              {state.benches.map((bench, index) => (
                <BenchCard
                  key={bench.id}
                  bench={bench}
                  onImageClick={handleImageClick}
                  onStreetViewClick={handleStreetViewClick}
                  animationDelay={index * 0.1}
                />
              ))}
            </BenchGrid>
          )}

          {/* Infinite scroll trigger */}
          {state.hasMore && state.benches.length > 0 && (
            <InfiniteScrollTrigger ref={infiniteScrollRef}>
              {state.loading && (
                <LoadingContainer $show={true}>
                  <LoadingSpinner />
                  <span style={{ marginLeft: "12px" }}>
                    Loading more benches...
                  </span>
                </LoadingContainer>
              )}
            </InfiniteScrollTrigger>
          )}
        </CardsContainer>
      </ViewContainer>

      {/* Map View */}
      <ViewContainer $show={state.viewMode === "map"}>
        <MapView />
      </ViewContainer>

      {/* Modal for bench details */}
      <Modal
        isOpen={modalOpen}
        onClose={handleModalClose}
        bench={selectedBench}
        imageUrl={selectedImageUrl}
        imageId={selectedImageId}
      />
    </PageContainer>
  )
}

export default HomePage
