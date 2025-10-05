import React, { useCallback, useEffect } from "react"
import { useInView } from "react-intersection-observer"
import { useSearchParams } from "react-router-dom"
import styled from "styled-components"
import type { WebBenchData } from "../api"
import BenchCard from "../components/BenchCard/BenchCard"
import Header from "../components/Header/Header"
import LoadingSpinner from "../components/LoadingSpinner/LoadingSpinner"
import Modal from "../components/Modal/Modal"
import { type AppFilters, useApp } from "../contexts/AppContext"
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

const CardsContainer = styled.div`
  max-width: 1400px;
  margin: 0 auto;
  padding: ${({ theme }) => theme.spacing[8]} ${({ theme }) => theme.spacing[5]};
  background: ${({ theme }) => theme.colors.backgroundSecondary};
  width: 100%;
  
  /* Ensure minimum width for grid layout */
  min-width: 0; /* Allow flexbox shrinking */
  
  @media (max-width: 640px) {
    padding: ${({ theme }) => theme.spacing[6]} ${({ theme }) => theme.spacing[4]};
  }
`

const BenchGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: ${({ theme }) => theme.spacing[6]};
  margin-bottom: ${({ theme }) => theme.spacing[10]};
  
  /* Mobile: Single column for very small screens */
  @media (max-width: 640px) {
    grid-template-columns: 1fr;
    gap: ${({ theme }) => theme.spacing[4]};
  }
  
  /* Tablet: Smaller minimum card width */
  @media (min-width: 641px) and (max-width: 1023px) {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: ${({ theme }) => theme.spacing[5]};
  }
  
  /* Desktop: Default card size */
  @media (min-width: 1024px) {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: ${({ theme }) => theme.spacing[6]};
  }
  
  /* Large desktop: Larger minimum card width */
  @media (min-width: 1280px) {
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: ${({ theme }) => theme.spacing[6]};
  }
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

const CardsPage: React.FC = () => {
  const { state, loadMoreBenches, updateFilters } = useApp()
  const [searchParams, _setSearchParams] = useSearchParams()
  const [selectedBench, setSelectedBench] = React.useState<WebBenchData | null>(
    null
  )
  const [selectedImageUrl, setSelectedImageUrl] = React.useState<string | null>(
    null
  )
  const [selectedImageId, setSelectedImageId] = React.useState<number | null>(
    null
  )
  const [modalOpen, setModalOpen] = React.useState(false)
  const [currentModalIndex, setCurrentModalIndex] = React.useState(0)

  // Intersection observer for infinite scroll
  const { ref: infiniteScrollRef, inView } = useInView({
    threshold: 0,
    rootMargin: "100px",
  })

  // Initialize filters from URL on mount - only run when config or searchParams change
  useEffect(() => {
    if (state.config) {
      const urlFilters = searchParamsToFilters(searchParams, state.filters)

      // Only update if filters actually differ from current state
      const hasChanges = Object.entries(urlFilters).some(([key, value]) => {
        return state.filters[key as keyof AppFilters] !== value
      })

      if (hasChanges) {
        updateFilters(urlFilters)
      }
    }
  }, [state.config, searchParams, updateFilters])

  // Update URL when filters change
  useEffect(() => {
    if (state.config) {
      updateUrlWithFilters(state.filters, "/cards")
    }
  }, [state.filters, state.config])

  // Load initial data when filters change or when navigating to cards view
  useEffect(() => {
    if (state.benches?.length === 0 && !state.loading && state.config) {
      loadMoreBenches()
    }
  }, [state.config, state.benches?.length, state.loading, loadMoreBenches])

  // Handle infinite scroll
  useEffect(() => {
    if (inView && state.hasMore && !state.loading) {
      loadMoreBenches()
    }
  }, [inView, state.hasMore, state.loading, loadMoreBenches])

  const handleImageClick = useCallback(
    (bench: WebBenchData, imageUrl: string, imageId: number) => {
      const benchIndex = state.benches?.findIndex((b) => b.id === bench.id) || 0
      setSelectedBench(bench)
      setSelectedImageUrl(imageUrl)
      setSelectedImageId(imageId)
      setCurrentModalIndex(benchIndex >= 0 ? benchIndex : 0)
      setModalOpen(true)
    },
    [state.benches]
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
    setCurrentModalIndex(0)
  }, [])

  const handleModalNavigate = useCallback(
    (direction: "prev" | "next") => {
      if (!state.benches || state.benches.length === 0) return

      let newIndex =
        direction === "prev" ? currentModalIndex - 1 : currentModalIndex + 1

      // Clamp to valid range
      newIndex = Math.max(0, Math.min(state.benches.length - 1, newIndex))

      console.log("Modal navigation:", {
        direction,
        currentIndex: currentModalIndex,
        newIndex,
        totalBenches: state.benches.length,
      })

      const newBench = state.benches[newIndex]
      if (
        newBench &&
        newBench.image_filenames &&
        newBench.image_filenames.length > 0
      ) {
        const firstImageFilename = newBench.image_filenames[0]
        const imageUrl = `/images/${firstImageFilename}`
        console.log("Navigating to bench:", {
          id: newBench.id,
          imageUrl: imageUrl,
        })
        setSelectedBench(newBench)
        setSelectedImageUrl(imageUrl)
        setSelectedImageId(newBench.image_ids?.[0] || 0)
        setCurrentModalIndex(newIndex)
      }
    },
    [currentModalIndex, state.benches]
  )

  const showNoResults =
    (state.benches?.length || 0) === 0 &&
    !state.loading &&
    state.currentPage > 0

  const showLoading = state.loading && (state.benches?.length || 0) === 0

  return (
    <PageContainer>
      <Header />

      <ViewContainer>
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

          {state.benches && state.benches.length > 0 && (
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
          {state.hasMore && state.benches && state.benches.length > 0 && (
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

      {/* Modal for bench details */}
      <Modal
        isOpen={modalOpen}
        onClose={handleModalClose}
        bench={selectedBench}
        imageUrl={selectedImageUrl}
        imageId={selectedImageId}
        allBenches={state.benches || []}
        currentIndex={currentModalIndex}
        onNavigate={handleModalNavigate}
      />
    </PageContainer>
  )
}

export default CardsPage
