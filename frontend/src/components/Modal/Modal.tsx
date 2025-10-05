import { AnimatePresence, motion } from "framer-motion"
import { ChevronLeft, ChevronRight, X } from "lucide-react"
import type React from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import styled from "styled-components"
import type { SegmentationData, WebBenchData } from "../../api"
import { benchApi } from "../../services/api"

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

const DetectionSection = styled.div<{ $color: string }>`
  border: 1px solid ${({ $color }) => $color};
  border-radius: ${({ theme }) => theme.borderRadius.base};
  padding: ${({ theme }) => theme.spacing[3]};
  margin-bottom: ${({ theme }) => theme.spacing[3]};
  background: ${({ $color }) => `${$color}08`};

  h5 {
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
    color: ${({ $color }) => $color};
    font-size: ${({ theme }) => theme.typography.sizes.base};
    font-weight: ${({ theme }) => theme.typography.weights.medium};
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
}) => {
  const [segmentationData, setSegmentationData] =
    useState<SegmentationData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const overlayRef = useRef<SVGSVGElement>(null)

  // Load segmentation data when imageId changes
  useEffect(() => {
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

      setLoading(true)
      setError(null)

      try {
        const data = await benchApi.getImageSegmentation(imageId)
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
  }, [imageId, isOpen])

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

    // Render segmentation polygons (Ultralytics)
    if (segmentationData.bench_detections?.length) {
      segmentationData.bench_detections.forEach((detection, index) => {
        if (detection.segments?.x && detection.segments?.y) {
          const points: string[] = []
          const scaleX = displayWidth / imageNaturalWidth
          const scaleY = displayHeight / imageNaturalHeight

          for (let i = 0; i < detection.segments.x.length; i++) {
            const x = detection.segments.x[i] * scaleX
            const y = detection.segments.y[i] * scaleY
            points.push(`${x},${y}`)
          }

          const polygon = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "polygon"
          )
          polygon.setAttribute("points", points.join(" "))
          polygon.setAttribute("class", "segmentation-polygon")
          polygon.style.fill = `rgba(76, 175, 80, ${0.3 + index * 0.1})`
          polygon.style.stroke = "#4caf50"
          polygon.style.strokeWidth = "2"

          overlay.appendChild(polygon)
        }
      })
    }

    // Render bounding boxes (Roboflow)
    if (segmentationData.roboflow_detections?.length) {
      segmentationData.roboflow_detections.forEach((detection, index) => {
        if (
          detection.x !== undefined &&
          detection.y !== undefined &&
          detection.width !== undefined &&
          detection.height !== undefined
        ) {
          const scaleX = displayWidth / imageNaturalWidth
          const scaleY = displayHeight / imageNaturalHeight

          const centerX = detection.x * scaleX
          const centerY = detection.y * scaleY
          const width = detection.width * scaleX
          const height = detection.height * scaleY
          const x = centerX - width / 2
          const y = centerY - height / 2

          const rect = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "rect"
          )
          rect.setAttribute("x", x.toString())
          rect.setAttribute("y", y.toString())
          rect.setAttribute("width", width.toString())
          rect.setAttribute("height", height.toString())
          rect.setAttribute("class", "bounding-box")
          rect.style.fill = `rgba(255, 193, 7, ${0.2 + index * 0.1})`
          rect.style.stroke = "#ff9800"
          rect.style.strokeWidth = "3"
          rect.style.strokeDasharray = "5,5"

          overlay.appendChild(rect)

          // Add confidence label
          if (detection.confidence) {
            const text = document.createElementNS(
              "http://www.w3.org/2000/svg",
              "text"
            )
            text.setAttribute("x", (x + 5).toString())
            text.setAttribute("y", (y - 5).toString())
            text.setAttribute("class", "detection-label")
            text.style.fill = "#ff9800"
            text.style.fontSize = "14px"
            text.style.fontWeight = "bold"
            text.style.textShadow = "1px 1px 2px rgba(0,0,0,0.8)"
            text.textContent = `${(detection.confidence * 100).toFixed(1)}%`

            overlay.appendChild(text)
          }
        }
      })
    }

    // Show the overlay
    overlay.style.display = "block"
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
            currentIndex < allBenches.length - 1
          )
          if (onNavigate && currentIndex < allBenches.length - 1) {
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
  }, [isOpen, onClose, onNavigate, currentIndex, allBenches.length])

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
  }

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
              <CloseButton onClick={onClose}>
                <X />
              </CloseButton>
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
                        disabled={currentIndex >= allBenches.length - 1}
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
                    style={{ display: segmentationData ? "block" : "none" }}
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
                        {(segmentationData.confidence_score * 100).toFixed(1)}%
                      </InfoValue>
                    </InfoRow>
                  </DetectionHeader>

                  {/* Ultralytics Segmentation Detections */}
                  {segmentationData.bench_detections &&
                    segmentationData.bench_detections.length > 0 && (
                      <>
                        <h5
                          style={{ color: "#4caf50", margin: "16px 0 12px 0" }}
                        >
                          🎯 Segmentation Detections (Ultralytics)
                        </h5>
                        {segmentationData.bench_detections.map(
                          (detection, index) => (
                            <DetectionSection key={index} $color="#4caf50">
                              <h5>Segmentation {index + 1}</h5>
                              <InfoRow>
                                <InfoLabel>Class:</InfoLabel>
                                <InfoValue>
                                  {detection.class || "Unknown"}
                                </InfoValue>
                              </InfoRow>
                              <InfoRow>
                                <InfoLabel>Confidence:</InfoLabel>
                                <InfoValue>
                                  {(detection.confidence * 100).toFixed(1)}%
                                </InfoValue>
                              </InfoRow>
                              {detection.segments && detection.segments.x && (
                                <InfoRow>
                                  <InfoLabel>Segmentation Points:</InfoLabel>
                                  <InfoValue>
                                    {detection.segments.x.length} coordinates
                                  </InfoValue>
                                </InfoRow>
                              )}
                              {detection.box && (
                                <InfoRow>
                                  <InfoLabel>Bounding Box:</InfoLabel>
                                  <InfoValue>
                                    x: {detection.box.x1}-{detection.box.x2}, y:{" "}
                                    {detection.box.y1}-{detection.box.y2}
                                  </InfoValue>
                                </InfoRow>
                              )}
                            </DetectionSection>
                          )
                        )}
                      </>
                    )}

                  {/* Roboflow Bounding Box Detections */}
                  {segmentationData.roboflow_detections &&
                    segmentationData.roboflow_detections.length > 0 && (
                      <>
                        <h5
                          style={{ color: "#ff9800", margin: "16px 0 12px 0" }}
                        >
                          📦 Bounding Box Detections (Roboflow)
                        </h5>
                        {segmentationData.roboflow_detections.map(
                          (detection, index) => (
                            <DetectionSection key={index} $color="#ff9800">
                              <h5>Bounding Box {index + 1}</h5>
                              <InfoRow>
                                <InfoLabel>Class:</InfoLabel>
                                <InfoValue>
                                  {detection.class || "bench"}
                                </InfoValue>
                              </InfoRow>
                              <InfoRow>
                                <InfoLabel>Confidence:</InfoLabel>
                                <InfoValue>
                                  {(detection.confidence * 100).toFixed(1)}%
                                </InfoValue>
                              </InfoRow>
                              <InfoRow>
                                <InfoLabel>Center:</InfoLabel>
                                <InfoValue>
                                  x: {detection.x?.toFixed(1)}, y:{" "}
                                  {detection.y?.toFixed(1)}
                                </InfoValue>
                              </InfoRow>
                              <InfoRow>
                                <InfoLabel>Size:</InfoLabel>
                                <InfoValue>
                                  w: {detection.width?.toFixed(1)}, h:{" "}
                                  {detection.height?.toFixed(1)}
                                </InfoValue>
                              </InfoRow>
                            </DetectionSection>
                          )
                        )}
                      </>
                    )}
                </DetectionInfo>
              )}
            </ModalContent>
          </ModalContainer>
        </Overlay>
      )}
    </AnimatePresence>
  )
}

export default Modal
