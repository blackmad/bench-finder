import { AnimatePresence, motion } from "framer-motion"
import { ChevronLeft, ChevronRight, ExternalLink, X } from "lucide-react"
import type React from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import styled from "styled-components"
import type { SegmentationData, WebBenchData } from "../../api"
import { benchApi } from "../../services/api"
import DetectionData from "../DetectionData/DetectionData"

const Overlay = styled(motion.div)`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: ${({ theme }) => theme.colors.overlay};
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: ${({ theme }) => theme.zIndex.modalBackdrop};
  padding: ${({ theme }) => theme.spacing[5]};
`

const ModalContainer = styled(motion.div)`
  position: relative;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  overflow: hidden;
  box-shadow: ${({ theme }) => theme.shadows["2xl"]};
  z-index: ${({ theme }) => theme.zIndex.modal};
`

const ModalHeader = styled.div`
  padding: ${({ theme }) => theme.spacing[5]};
  background: ${({ theme }) => theme.colors.backgroundTertiary};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  display: flex;
  justify-content: space-between;
  align-items: center;
`

const ModalTitle = styled.h2`
  margin: 0;
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
`

const CloseButton = styled.button`
  background: none;
  border: none;
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  cursor: pointer;
  color: ${({ theme }) => theme.colors.textSecondary};
  padding: ${({ theme }) => theme.spacing[2]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  transition: all ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ theme }) => theme.colors.gray200};
  }

  svg {
    width: 24px;
    height: 24px;
  }
`

const PermalinkButton = styled(Link)`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  text-decoration: none;
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[3]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  transition: all ${({ theme }) => theme.transitions.fast};
  margin-left: ${({ theme }) => theme.spacing[3]};

  &:hover {
    background: ${({ theme }) => theme.colors.primaryDark};
    transform: translateY(-1px);
  }

  svg {
    width: 16px;
    height: 16px;
  }
`

const ModalHeaderActions = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
`

const ModalContent = styled.div`
  padding: ${({ theme }) => theme.spacing[5]};
  overflow-y: auto;
  max-height: calc(90vh - 120px);
`

const ImageContainer = styled.div`
  position: relative;
  display: flex;
  justify-content: center;
  background: ${({ theme }) => theme.colors.gray900};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  overflow: hidden;
  margin-bottom: ${({ theme }) => theme.spacing[5]};
`

const ModalImage = styled.img`
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
`

const SegmentationOverlay = styled.svg`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 2;
`

const NavigationArrow = styled.button<{ direction: "prev" | "next" }>`
  position: absolute;
  top: 50%;
  ${({ direction }) => (direction === "prev" ? "left: 20px;" : "right: 20px;")}
  transform: translateY(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: white;
  border: none;
  font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[4]};
  cursor: pointer;
  z-index: 1000; /* Increased z-index to ensure visibility above overlay */
  transition: all ${({ theme }) => theme.transitions.normal};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  min-height: 48px;

  /* Ensure arrows are visible */
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);

  &:hover {
    background: rgba(0, 0, 0, 0.9);
    transform: translateY(-50%) scale(1.05);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;

    &:hover {
      transform: translateY(-50%);
      background: rgba(0, 0, 0, 0.8);
    }
  }

  svg {
    width: 28px;
    height: 28px;
  }
`

const DetectionInfo = styled.div`
  margin-top: ${({ theme }) => theme.spacing[5]};
  padding: ${({ theme }) => theme.spacing[4]};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ theme }) => theme.colors.backgroundTertiary};
`

const DetectionHeader = styled.div`
  border-bottom: 2px solid ${({ theme }) => theme.colors.primary};
  padding-bottom: ${({ theme }) => theme.spacing[3]};
  margin-bottom: ${({ theme }) => theme.spacing[4]};

  h4 {
    margin: 0;
    color: ${({ theme }) => theme.colors.primary};
    font-size: ${({ theme }) => theme.typography.sizes.lg};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
  }
`


const PlaceholderContent = styled.div`
  text-align: center;
  padding: ${({ theme }) => theme.spacing[10]};
  color: ${({ theme }) => theme.colors.textSecondary};

  .icon {
    font-size: ${({ theme }) => theme.typography.sizes["4xl"]};
    margin-bottom: ${({ theme }) => theme.spacing[4]};
  }
`

const BenchInfo = styled.div`
  display: grid;
  gap: ${({ theme }) => theme.spacing[3]};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
`

const InfoRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: ${({ theme }) => theme.spacing[2]} 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};

  &:last-child {
    border-bottom: none;
  }
`

const InfoLabel = styled.span`
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  color: ${({ theme }) => theme.colors.textSecondary};
`

const InfoValue = styled.span`
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.typography.fonts.mono};
`

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  bench: WebBenchData | null
  imageUrl: string | null
  imageId: number | null
  // Navigation props
  allBenches?: WebBenchData[]
  currentIndex?: number
  onNavigate?: (direction: "prev" | "next") => void
  hasMore?: boolean // Whether there are more benches that can be loaded
}

const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  bench,
  imageUrl,
  imageId,
  allBenches = [],
  currentIndex = 0,
  onNavigate,
  hasMore = false,
}) => {
  const [segmentationData, setSegmentationData] =
    useState<SegmentationData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const overlayRef = useRef<SVGSVGElement>(null)
  // Cache for segmentation data to avoid re-fetching
  const segmentationCacheRef = useRef<Map<number, SegmentationData>>(new Map())

  // Load segmentation data when imageId changes
  useEffect(() => {
    // Immediately hide overlay when imageId/imageUrl changes to prevent leftover bounce
    if (overlayRef.current) {
      overlayRef.current.style.display = "none"
      overlayRef.current.innerHTML = ""
    }
    setSegmentationData(null)

    const loadSegmentationData = async () => {
      if (!imageId || !isOpen) {
        setSegmentationData(null)
        // Hide overlay when no data
        if (overlayRef.current) {
          overlayRef.current.style.display = "none"
          overlayRef.current.innerHTML = ""
        }
        return
      }

      // Check cache first
      const cached = segmentationCacheRef.current.get(imageId)
      if (cached) {
        setSegmentationData(cached)
        return
      }

      setLoading(true)
      setError(null)

      try {
        const data = await benchApi.getImageSegmentation(imageId)
        // Cache the data
        segmentationCacheRef.current.set(imageId, data)
        setSegmentationData(data)
      } catch (err) {
        console.warn("No segmentation data available for image:", imageId)
        setError("No segmentation data available for this image")
        setSegmentationData(null)
        // Hide overlay when no data
        if (overlayRef.current) {
          overlayRef.current.style.display = "none"
          overlayRef.current.innerHTML = ""
        }
      } finally {
        setLoading(false)
      }
    }

    loadSegmentationData()
  }, [imageId, imageUrl, isOpen])

  // Pre-load segmentation data for adjacent images
  useEffect(() => {
    if (!isOpen || allBenches.length === 0) return

    const preloadSegmentation = async (imageId: number) => {
      // Skip if already cached or loading
      if (segmentationCacheRef.current.has(imageId)) return

      try {
        const data = await benchApi.getImageSegmentation(imageId)
        segmentationCacheRef.current.set(imageId, data)
      } catch (err) {
        // Silently fail for pre-loading - we'll handle errors when actually loading
        console.debug("Pre-load segmentation failed for image:", imageId)
      }
    }

    // Pre-load previous image segmentation
    if (currentIndex > 0) {
      const prevBench = allBenches[currentIndex - 1]
      const prevImageId = prevBench?.image_ids?.[0]
      if (prevImageId) {
        preloadSegmentation(prevImageId)
      }
    }

    // Pre-load next image segmentation
    if (currentIndex < allBenches.length - 1) {
      const nextBench = allBenches[currentIndex + 1]
      const nextImageId = nextBench?.image_ids?.[0]
      if (nextImageId) {
        preloadSegmentation(nextImageId)
      }
    }
  }, [isOpen, allBenches, currentIndex])

  // Render segmentation overlays when image loads
  const renderSegmentationOverlays = useCallback(() => {
    if (!imageRef.current || !overlayRef.current || !segmentationData) {
      return
    }

    const image = imageRef.current
    const overlay = overlayRef.current
    const container = image.parentElement

    if (!container) {
      return
    }

    // Check if image is loaded
    if (
      !image.complete ||
      image.naturalWidth === 0 ||
      image.naturalHeight === 0
    ) {
      return
    }

    // Clear previous overlays
    overlay.innerHTML = ""

    // Calculate image display dimensions accounting for object-fit: contain
    const containerRect = container.getBoundingClientRect()
    const imageNaturalWidth = image.naturalWidth
    const imageNaturalHeight = image.naturalHeight
    const containerAspect = containerRect.width / containerRect.height
    const imageAspect = imageNaturalWidth / imageNaturalHeight

    let displayWidth: number
    let displayHeight: number
    let offsetX: number
    let offsetY: number

    if (imageAspect > containerAspect) {
      // Image is wider than container - limited by width
      displayWidth = containerRect.width
      displayHeight = containerRect.width / imageAspect
      offsetX = 0
      offsetY = (containerRect.height - displayHeight) / 2
    } else {
      // Image is taller than container - limited by height
      displayWidth = containerRect.height * imageAspect
      displayHeight = containerRect.height
      offsetX = (containerRect.width - displayWidth) / 2
      offsetY = 0
    }

    // Set overlay dimensions and position
    overlay.style.width = displayWidth + "px"
    overlay.style.height = displayHeight + "px"
    overlay.style.left = offsetX + "px"
    overlay.style.top = offsetY + "px"
    overlay.setAttribute("viewBox", `0 0 ${displayWidth} ${displayHeight}`)

    // Get image shape from segmentation data or use natural dimensions
    const imageShape = segmentationData.image_shape || [
      imageNaturalWidth,
      imageNaturalHeight,
    ]
    const imageWidth = imageShape[0] || imageNaturalWidth
    const imageHeight = imageShape[1] || imageNaturalHeight

    // Calculate scale factors from natural image size to display size
    const scaleX = displayWidth / imageWidth
    const scaleY = displayHeight / imageHeight

    // Render detection items
    const detectionItems = segmentationData.detection_items
    const hasItems =
      detectionItems && detectionItems.length > 0
    let hasRenderedItems = false

    if (hasItems && detectionItems) {
      detectionItems.forEach((item, index) => {
        // Prefer polygon (segmentation) over bounding box
        if (item.polygon && item.polygon.coordinates && item.polygon.coordinates.length > 0) {
          // Render segmentation polygon
          const points = item.polygon.coordinates
            .map(([x, y]) => `${x * scaleX},${y * scaleY}`)
            .join(" ")

          const polygon = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "polygon"
          )
          polygon.setAttribute("points", points)
          polygon.setAttribute("fill", "rgba(59, 130, 246, 0.3)") // Blue fill with transparency
          polygon.setAttribute("stroke", "#3b82f6") // Blue border
          polygon.setAttribute("stroke-width", "2")
          polygon.setAttribute("stroke-linejoin", "round")
          polygon.setAttribute(
            "data-detection-id",
            item.detection_id?.toString() || index.toString()
          )

          overlay.appendChild(polygon)
          hasRenderedItems = true
        } else if (item.bbox) {
          // Render bounding box
          const { x1, y1, x2, y2 } = item.bbox
          const rectX = x1 * scaleX
          const rectY = y1 * scaleY
          const rectWidth = (x2 - x1) * scaleX
          const rectHeight = (y2 - y1) * scaleY

          const rect = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "rect"
          )
          rect.setAttribute("x", rectX.toString())
          rect.setAttribute("y", rectY.toString())
          rect.setAttribute("width", rectWidth.toString())
          rect.setAttribute("height", rectHeight.toString())
          rect.setAttribute("fill", "rgba(34, 197, 94, 0.2)") // Green fill with transparency
          rect.setAttribute("stroke", "#22c55e") // Green border
          rect.setAttribute("stroke-width", "2")
          rect.setAttribute("rx", "4") // Rounded corners
          rect.setAttribute(
            "data-detection-id",
            item.detection_id?.toString() || index.toString()
          )

          overlay.appendChild(rect)
          hasRenderedItems = true
        }
      })
    }

    // Show or hide overlay based on whether we rendered anything
    overlay.style.display = hasRenderedItems ? "block" : "none"
  }, [segmentationData])

  // Handle image load to render overlays
  const handleImageLoad = useCallback(() => {
    // Small delay to ensure layout has settled
    setTimeout(() => {
      renderSegmentationOverlays()
    }, 100)
  }, [renderSegmentationOverlays])

  // Handle rendering when segmentation data changes
  useEffect(() => {
    if (segmentationData && imageRef.current && overlayRef.current) {
      // If image is already loaded (cached), render with delay
      if (imageRef.current.complete && imageRef.current.naturalWidth > 0) {
        setTimeout(() => {
          renderSegmentationOverlays()
        }, 100)
      }
    }
  }, [segmentationData, renderSegmentationOverlays])

  // Handle window resize to re-render overlays
  useEffect(() => {
    if (!isOpen) return

    const handleResize = () => {
      if (segmentationData && imageRef.current && overlayRef.current) {
        setTimeout(() => {
          renderSegmentationOverlays()
        }, 100)
      }
    }

    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [isOpen, segmentationData, renderSegmentationOverlays])

  // Handle keyboard navigation and modal controls
  useEffect(() => {
    let lastKeyTime = 0

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isOpen) return

      console.log("Modal key pressed:", event.key, {
        onNavigate: !!onNavigate,
        currentIndex,
        totalBenches: allBenches.length,
      })

      switch (event.key) {
        case "Escape":
          onClose()
          break
        case "ArrowLeft": {
          event.preventDefault()
          // Simple debounce to prevent rapid-fire navigation
          const now = Date.now()
          if (now - lastKeyTime < 100) return
          lastKeyTime = now

          console.log("Left arrow - can navigate prev:", currentIndex > 0)
          if (onNavigate && currentIndex > 0) {
            console.log("Navigating to previous bench")
            onNavigate("prev")
          }
          break
        }
        case "ArrowRight": {
          event.preventDefault()
          // Simple debounce to prevent rapid-fire navigation
          const nowRight = Date.now()
          if (nowRight - lastKeyTime < 100) return
          lastKeyTime = nowRight

          console.log(
            "Right arrow - can navigate next:",
            currentIndex < allBenches.length - 1 || hasMore
          )
          if (
            onNavigate &&
            (currentIndex < allBenches.length - 1 || hasMore)
          ) {
            console.log("Navigating to next bench")
            onNavigate("next")
          }
          break
        }
      }
    }

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown)
      document.body.style.overflow = "hidden"
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      document.body.style.overflow = "unset"
    }
  }, [isOpen, onClose, onNavigate, currentIndex, allBenches.length, hasMore])

  if (!bench) {
    return null
  }

  const overlayVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
    exit: { opacity: 0 },
  }

  const modalVariants = {
    hidden: { opacity: 0, scale: 0.95, y: 20 },
    visible: {
      opacity: 1,
      scale: 1,
      y: 0,
      transition: {
        type: "spring",
        stiffness: 300,
        damping: 30,
      },
    },
    exit: {
      opacity: 0,
      scale: 0.95,
      y: 20,
      transition: {
        duration: 0.2,
      },
    },
  } as const

  return (
    <AnimatePresence>
      {isOpen && (
        <Overlay
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={onClose}
        >
          <ModalContainer
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={(e) => e.stopPropagation()}
          >
            <ModalHeader>
              <ModalTitle>
                Bench #{bench.id} - Detection Details
                {allBenches.length > 1 && (
                  <span
                    style={{
                      fontSize: "0.8em",
                      fontWeight: "normal",
                      marginLeft: "12px",
                      color: "#64748b",
                    }}
                  >
                    ({currentIndex + 1} of {allBenches.length})
                  </span>
                )}
              </ModalTitle>
              <ModalHeaderActions>
                <PermalinkButton to={`/bench/${bench.id}`}>
                  <ExternalLink />
                  View Full Page
                </PermalinkButton>
                <CloseButton onClick={onClose}>
                  <X />
                </CloseButton>
              </ModalHeaderActions>
            </ModalHeader>

            <ModalContent>
              {imageUrl ? (
                <ImageContainer>
                  {/* Navigation arrows - only show if we have multiple benches */}
                  {onNavigate && allBenches.length > 1 && (
                    <>
                      <NavigationArrow
                        direction="prev"
                        onClick={() => {
                          console.log("Previous arrow clicked")
                          onNavigate("prev")
                        }}
                        disabled={currentIndex <= 0}
                        title="Previous bench (←)"
                      >
                        <ChevronLeft />
                      </NavigationArrow>
                      <NavigationArrow
                        direction="next"
                        onClick={() => {
                          console.log("Next arrow clicked")
                          onNavigate("next")
                        }}
                        disabled={
                          currentIndex >= allBenches.length - 1 && !hasMore
                        }
                        title="Next bench (→)"
                      >
                        <ChevronRight />
                      </NavigationArrow>
                    </>
                  )}

                  <ModalImage
                    ref={imageRef}
                    src={imageUrl}
                    alt={`Bench ${bench.id}`}
                    onLoad={handleImageLoad}
                  />
                  <SegmentationOverlay
                    ref={overlayRef}
                    style={{
                      display:
                        segmentationData &&
                          segmentationData.detection_items &&
                          segmentationData.detection_items.length > 0
                          ? "block"
                          : "none",
                    }}
                  />
                </ImageContainer>
              ) : (
                <PlaceholderContent>
                  <div className="icon">🪑</div>
                  <p>No image available for this bench</p>
                </PlaceholderContent>
              )}

              <BenchInfo>
                <InfoRow>
                  <InfoLabel>Bench ID:</InfoLabel>
                  <InfoValue>#{bench.id}</InfoValue>
                </InfoRow>
                <InfoRow>
                  <InfoLabel>Location:</InfoLabel>
                  <InfoValue>
                    {bench.lat.toFixed(6)}, {bench.lng.toFixed(6)}
                  </InfoValue>
                </InfoRow>
                <InfoRow>
                  <InfoLabel>Distance:</InfoLabel>
                  <InfoValue>
                    {bench.distance_km < 1
                      ? `${bench.distance_meters}m`
                      : `${bench.distance_km}km`}
                  </InfoValue>
                </InfoRow>
                <InfoRow>
                  <InfoLabel>Best Confidence:</InfoLabel>
                  <InfoValue>
                    {(bench.best_confidence * 100).toFixed(1)}%
                  </InfoValue>
                </InfoRow>
                <InfoRow>
                  <InfoLabel>Detection Type:</InfoLabel>
                  <InfoValue style={{ textTransform: "capitalize" }}>
                    {bench.detection_type}
                  </InfoValue>
                </InfoRow>
                <InfoRow>
                  <InfoLabel>Source:</InfoLabel>
                  <InfoValue style={{ textTransform: "uppercase" }}>
                    {bench.source}
                  </InfoValue>
                </InfoRow>
                <InfoRow>
                  <InfoLabel>Image Count:</InfoLabel>
                  <InfoValue>{bench.image_count}</InfoValue>
                </InfoRow>
                {bench.has_segmentation && (
                  <InfoRow>
                    <InfoLabel>Segmentation:</InfoLabel>
                    <InfoValue>Available</InfoValue>
                  </InfoRow>
                )}
              </BenchInfo>

              {/* Segmentation and Detection Details */}
              {loading && (
                <PlaceholderContent>
                  <div className="icon">🔄</div>
                  <p>Loading detection details...</p>
                </PlaceholderContent>
              )}

              {error && !loading && (
                <PlaceholderContent>
                  <div className="icon">⚠️</div>
                  <p>{error}</p>
                </PlaceholderContent>
              )}

              {segmentationData && !loading && (
                <DetectionInfo>
                  <DetectionHeader>
                    <h4>🎯 Detection Analysis</h4>
                    <InfoRow>
                      <InfoLabel>Detection Type:</InfoLabel>
                      <InfoValue
                        style={{ textTransform: "capitalize", fontWeight: 600 }}
                      >
                        {segmentationData.detection_type}
                      </InfoValue>
                    </InfoRow>
                    <InfoRow>
                      <InfoLabel>Source:</InfoLabel>
                      <InfoValue
                        style={{ textTransform: "capitalize", fontWeight: 600 }}
                      >
                        {segmentationData.source}
                      </InfoValue>
                    </InfoRow>
                    <InfoRow>
                      <InfoLabel>Max Confidence:</InfoLabel>
                      <InfoValue style={{ fontWeight: 600 }}>
                        {((segmentationData.confidence_score || 0) * 100).toFixed(1)}%
                      </InfoValue>
                    </InfoRow>
                  </DetectionHeader>

                  {/* Detection data is now handled by the DetectionData component */}
                </DetectionInfo>
              )}

              {/* Show detection data if available */}
              {bench.detection_items && bench.detection_items.length > 0 && (
                <DetectionData
                  detectionItems={bench.detection_items}
                  detectionSource={bench.detection_type}
                />
              )}
            </ModalContent>
          </ModalContainer>
        </Overlay>
      )}
    </AnimatePresence>
  )
}

export default Modal
