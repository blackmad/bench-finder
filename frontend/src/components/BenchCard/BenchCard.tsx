import { motion } from "framer-motion"
import L from "leaflet"
import { Flag, Hash, MapPin, Target } from "lucide-react"
import type React from "react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import styled, { keyframes } from "styled-components"
import type { StructuredAddress, WebBenchData } from "../../api"
import { DataSource, DetectionSource } from "../../api"
import { useApp } from "../../contexts/AppContext"
import ReportModal from "../ReportModal/ReportModal"
import "leaflet/dist/leaflet.css"
import "../../utils/leafletFix"

// Helper function to format structured address for display
function formatStructuredAddress(
  addr: StructuredAddress | null | undefined
): string {
  if (!addr) return ""

  // Build address from components, fallback to formatted_address
  const parts: string[] = []

  if (addr.street_number && addr.street_name) {
    parts.push(`${addr.street_number} ${addr.street_name}`)
  } else if (addr.street_name) {
    parts.push(addr.street_name)
  }

  if (addr.city) {
    parts.push(addr.city)
  }

  if (addr.state) {
    if (addr.postal_code) {
      parts.push(`${addr.state} ${addr.postal_code}`)
    } else {
      parts.push(addr.state)
    }
  } else if (addr.postal_code) {
    parts.push(addr.postal_code)
  }

  if (addr.country) {
    parts.push(addr.country)
  }

  // Use formatted address if we have few components, otherwise use our formatted version
  if (parts.length > 0) {
    return parts.join(", ")
  }

  return addr.formatted_address || ""
}

const fadeInUp = keyframes`
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`

const CardContainer = styled(motion.div)`
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius["3xl"] || theme.borderRadius["2xl"]};
  overflow: hidden;
  box-shadow: ${({ theme }) => theme.shadows.base};
  border: 1px solid ${({ theme }) => theme.colors.border};
  transition: all ${({ theme }) => theme.transitions.normal};
  animation: ${fadeInUp} 0.4s ${({ theme }) => theme.easing.easeOut} forwards;
  opacity: 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;

  &:hover {
    transform: translateY(-4px);
    box-shadow: ${({ theme }) => theme.shadows.xl};
    border-color: ${({ theme }) => theme.colors.border};
  }
`

const ImageContainer = styled.div`
  position: relative;
  height: 240px;
  overflow: hidden;
  background: ${({ theme }) => theme.colors.gray100};
  cursor: pointer;
`

const BenchImage = styled.img`
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform ${({ theme }) => theme.transitions.slow};

  ${CardContainer}:hover & {
    transform: scale(1.05);
  }
`

const PlaceholderImage = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: ${({ theme }) => theme.colors.gray100};
  color: ${({ theme }) => theme.colors.gray400};
  font-size: ${({ theme }) => theme.typography.sizes["3xl"]};
`

const HoverOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.6) 0%, rgba(0, 0, 0, 0.2) 50%, transparent 100%);
  opacity: 0;
  transition: opacity ${({ theme }) => theme.transitions.normal};
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 120px;
  padding-left: ${({ theme }) => theme.spacing[4]};
  padding-right: 140px;
  color: white;
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  text-align: center;
  pointer-events: none;
  z-index: 1;

  ${ImageContainer}:hover & {
    opacity: 1;
  }
`

const Badge = styled.div<{
  $variant: "confidence" | "distance" | "detection" | "source" | "segmentation"
}>`
  position: absolute;
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[3]};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  text-transform: uppercase;
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

  ${({ $variant, theme }) => {
    switch ($variant) {
      case "confidence":
        return `
          top: ${theme.spacing[12]};
          right: ${theme.spacing[4]};
          background: ${theme.colors.success};
          color: white;
        `
      case "distance":
        return `
          top: ${theme.spacing[4]};
          right: ${theme.spacing[4]};
          background: rgba(255, 255, 255, 0.95);
          color: ${theme.colors.textPrimary};
          border: 1px solid rgba(255, 255, 255, 0.8);
        `
      case "detection":
        return `
          bottom: ${theme.spacing[4]};
          left: ${theme.spacing[4]};
          background: ${theme.colors.ultralytics};
          color: white;
        `
      case "source":
        return `
          top: ${theme.spacing[20]};
          right: ${theme.spacing[4]};
          background: ${theme.colors.gray600};
          color: white;
        `
      case "segmentation":
        return `
          bottom: ${theme.spacing[4]};
          right: ${theme.spacing[4]};
          background: ${theme.colors.warning};
          color: white;
        `
    }
  }}
`

const DebugBadge = styled(Badge)<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "block" : "none")};
`

const CardContent = styled.div`
  padding: ${({ theme }) => theme.spacing[6]};
`

const BenchTitle = styled.h3`
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin: 0 0 ${({ theme }) => theme.spacing[3]} 0;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  cursor: pointer;
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }

  svg {
    width: 20px;
    height: 20px;
  }
`

const BenchTitleLink = styled(Link)`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  text-decoration: none;
  color: inherit;
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }

  svg {
    width: 20px;
    height: 20px;
  }
`

const BenchDetails = styled.div`
  display: grid;
  gap: ${({ theme }) => theme.spacing[2]};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  color: ${({ theme }) => theme.colors.textSecondary};
`

const DetailRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`

const DetailLabel = styled.span`
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};

  svg {
    width: 14px;
    height: 14px;
  }
`

const DetailValue = styled.span`
  font-family: ${({ theme }) => theme.typography.fonts.mono};
  color: ${({ theme }) => theme.colors.textTertiary};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
`

const DebugDetails = styled.div<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "grid" : "none")};
  gap: ${({ theme }) => theme.spacing[2]};
  margin-top: ${({ theme }) => theme.spacing[4]};
  padding-top: ${({ theme }) => theme.spacing[4]};
  border-top: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const ConfidenceBar = styled.div<{ $confidence: number; $type: string }>`
  width: 100%;
  height: 4px;
  background: ${({ theme }) => theme.colors.gray200};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  overflow: hidden;
  margin-top: ${({ theme }) => theme.spacing[1]};

  &::after {
    content: '';
    display: block;
    height: 100%;
    width: ${({ $confidence }) => $confidence * 100}%;
    background: ${({ $type, theme }) => {
      switch ($type) {
        case "ultralytics":
          return theme.colors.ultralytics
        case "roboflow":
          return theme.colors.roboflow
        case "mapillary":
          return theme.colors.mapillary
        default:
          return theme.colors.primary
      }
    }};
    transition: width ${({ theme }) => theme.transitions.normal};
  }
`

const Tags = styled.div`
  margin-top: ${({ theme }) => theme.spacing[4]};
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing[2]};
`

const Tag = styled.span`
  display: inline-block;
  background: ${({ theme }) => theme.colors.gray100};
  color: ${({ theme }) => theme.colors.gray600};
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[2]};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
`

const ReportButton = styled.button`
  position: absolute;
  top: ${({ theme }) => theme.spacing[4]};
  left: ${({ theme }) => theme.spacing[4]};
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: ${({ theme }) => theme.borderRadius.full};
  padding: ${({ theme }) => theme.spacing[2]};
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
  opacity: 0;
  transform: translateY(-4px);
  transition: all ${({ theme }) => theme.transitions.normal};
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: ${({ theme }) => theme.shadows.md};
  z-index: 5;

  ${CardContainer}:hover & {
    opacity: 1;
    transform: translateY(0);
  }

  &:hover {
    background: rgba(255, 255, 255, 1);
    color: ${({ theme }) => theme.colors.warning};
    border-color: ${({ theme }) => theme.colors.warning};
    box-shadow: ${({ theme }) => theme.shadows.lg};
    transform: scale(1.1);
  }

  &:active {
    transform: scale(0.95);
  }

  svg {
    width: 16px;
    height: 16px;
  }
`

const HoverMap = styled.div`
  position: absolute;
  right: ${({ theme }) => theme.spacing[3]};
  bottom: ${({ theme }) => theme.spacing[3]};
  width: 120px;
  height: 90px;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  overflow: hidden;
  box-shadow: ${({ theme }) => theme.shadows.xl};
  opacity: 0;
  transform: translateY(6px);
  transition: all ${({ theme }) => theme.transitions.normal};
  border: 2px solid rgba(255, 255, 255, 0.85);
  z-index: 2;
  background: ${({ theme }) => theme.colors.gray200};

  ${ImageContainer}:hover & {
    opacity: 1;
    transform: translateY(0);
  }

  /* Ensure leaflet controls don't show in minimap */
  .leaflet-control-container {
    display: none !important;
  }

  .leaflet-attribution-flag {
    display: none !important;
  }

  .leaflet-control-attribution {
    display: none !important;
  }
`

const MiniMapPlaceholder = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #64748b;
  background: ${({ theme }) => theme.colors.gray100};
`

// Global styles for minimap marker
const GlobalMiniMapStyles = styled.div`
  .bench-minimap-marker {
    background: none !important;
    border: none !important;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    line-height: 1;
  }
`

interface BenchCardProps {
  bench: WebBenchData
  onImageClick?: (
    bench: WebBenchData,
    imageUrl: string,
    imageId: number
  ) => void
  onStreetViewClick?: (lat: number, lng: number) => void
  animationDelay?: number
}

export const BenchCard: React.FC<BenchCardProps> = ({
  bench,
  onImageClick,
  animationDelay = 0,
}) => {
  const { state } = useApp()
  const [hoverMapLoaded, setHoverMapLoaded] = useState(false)
  const [miniMap, setMiniMap] = useState<L.Map | null>(null)
  const [mapMarker, setMapMarker] = useState<L.Marker | null>(null)
  const [isReportModalOpen, setIsReportModalOpen] = useState(false)
  const mapRef = useRef<HTMLDivElement>(null)

  // Get primary image
  const imageUrl = bench.image_filenames?.[0]
    ? `/images/${bench.image_filenames[0]}`
    : null
  const imageId = bench.image_ids?.[0] || null

  // Format tags (exclude amenity tag and null values)
  const tags = Object.entries(bench.tags || {})
    .filter(
      ([key, value]) => key !== "amenity" && value != null && value !== "null"
    )
    .map(([key, value]) => `${key}: ${value}`)

  // Determine detection type color
  const getDetectionTypeColor = (type: DetectionSource) => {
    switch (type) {
      case DetectionSource.ULTRALYTICS:
        return "#059669"
      case DetectionSource.ROBOFLOW:
        return "#2563eb"
      case DetectionSource.MAPILLARY:
        return "#ea580c"
      case DetectionSource.MULTI_MODEL:
        return "#7c3aed"
      case DetectionSource.NONE:
        return "#6b7280"
      default:
        return "#6b7280"
    }
  }

  // Get source display name
  const getSourceDisplayName = (source: DataSource) => {
    switch (source) {
      case DataSource.OSM:
        return "OSM"
      case DataSource.MAPILLARY:
        return "Mapillary"
      default:
        return source
    }
  }

  const handleImageClick = () => {
    if (imageUrl && imageId && onImageClick) {
      onImageClick(bench, imageUrl, imageId)
    }
  }

  // Initialize minimap once
  useEffect(() => {
    if (!mapRef.current || miniMap) return

    // Small delay to ensure DOM is ready
    const initMap = () => {
      if (!mapRef.current || miniMap) return

      try {
        const map = L.map(mapRef.current, {
          center: [bench.lat, bench.lng],
          zoom: 12,
          zoomControl: false,
          attributionControl: false,
          scrollWheelZoom: false,
          doubleClickZoom: false,
          boxZoom: false,
          keyboard: false,
          dragging: false,
          touchZoom: false,
        })

        // Use CartoDB Positron No Labels for a clean look without labels
        L.tileLayer(
          "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png",
          {
            attribution: "",
          }
        ).addTo(map)

        // Add a pin marker for the bench
        const pinIcon = L.divIcon({
          html: "📍",
          className: "bench-minimap-marker",
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        })

        const marker = L.marker([bench.lat, bench.lng], {
          icon: pinIcon,
        }).addTo(map)

        // Invalidate size after a brief delay to ensure proper rendering
        setTimeout(() => {
          map.invalidateSize()
        }, 150)

        setMiniMap(map)
        setMapMarker(marker)
        setHoverMapLoaded(true)
      } catch (error) {
        console.warn("Failed to initialize minimap:", error)
      }
    }

    // Use requestAnimationFrame to ensure DOM is ready
    const timeoutId = setTimeout(initMap, 100)

    return () => {
      clearTimeout(timeoutId)
    }
  }, [bench.lat, bench.lng, miniMap])

  // Update map position when coordinates change
  useEffect(() => {
    if (miniMap && mapMarker) {
      miniMap.setView([bench.lat, bench.lng], 12)
      mapMarker.setLatLng([bench.lat, bench.lng])
    }
  }, [bench.lat, bench.lng, miniMap, mapMarker])

  // Cleanup minimap on unmount
  useEffect(() => {
    return () => {
      if (miniMap) {
        miniMap.remove()
        setMiniMap(null)
      }
      if (mapMarker) {
        mapMarker.remove()
        setMapMarker(null)
      }
    }
  }, [miniMap, mapMarker])

  const cardVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0 },
  }

  return (
    <GlobalMiniMapStyles>
      <CardContainer
        variants={cardVariants}
        initial="hidden"
        animate="visible"
        transition={{
          duration: 0.4,
          delay: animationDelay,
          ease: "easeOut",
        }}
      >
        <ImageContainer onClick={handleImageClick}>
          {imageUrl ? (
            <BenchImage
              src={imageUrl}
              alt={`Bench ${bench.id}`}
              loading="lazy"
            />
          ) : (
            <PlaceholderImage>🪑</PlaceholderImage>
          )}

          <ReportButton
            onClick={(e) => {
              e.stopPropagation()
              setIsReportModalOpen(true)
            }}
            title="Report issue with this bench"
          >
            <Flag />
          </ReportButton>

          <HoverOverlay>
            <div>
              View bench details
              <br />
              <small>Click to see detection data</small>
            </div>
          </HoverOverlay>

          {/* Distance Badge */}
          <Badge $variant="distance">
            {bench.distance_km < 1
              ? `${bench.distance_meters}m`
              : `${bench.distance_km}km`}
          </Badge>

          {/* Confidence Badge */}
          <DebugBadge $variant="confidence" $show={state.debugMode}>
            {(bench.best_confidence * 100).toFixed(0)}%
          </DebugBadge>

          {/* Detection Type Badge */}
          <DebugBadge $variant="detection" $show={state.debugMode}>
            {bench.detection_type}
          </DebugBadge>

          {/* Source Badge */}
          <DebugBadge $variant="source" $show={state.debugMode}>
            {getSourceDisplayName(bench.source)}
          </DebugBadge>

          {/* Segmentation Badge */}
          {bench.has_segmentation && (
            <DebugBadge $variant="segmentation" $show={state.debugMode}>
              🎯 SEG
            </DebugBadge>
          )}

          {/* Hover Map */}
          <HoverMap>
            <div ref={mapRef} style={{ width: "100%", height: "100%" }} />
            {!hoverMapLoaded && (
              <MiniMapPlaceholder
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                }}
              >
                📍 Map Preview
              </MiniMapPlaceholder>
            )}
          </HoverMap>
        </ImageContainer>

        <CardContent>
          <BenchTitle>
            <BenchTitleLink to={`/bench/${bench.id}`}>
              <MapPin />
              Bench #{bench.id}
            </BenchTitleLink>
          </BenchTitle>

          <BenchDetails>
            <DetailRow>
              <DetailLabel>
                <Hash />
                OSM ID:
              </DetailLabel>
              <DetailValue>{bench.provider_id}</DetailValue>
            </DetailRow>
            <DetailRow>
              <DetailLabel>
                <Target />
                Location:
              </DetailLabel>
              <DetailValue>
                {bench.lat.toFixed(6)}, {bench.lng.toFixed(6)}
              </DetailValue>
            </DetailRow>
            {bench.reverse_geocode && (
              <DetailRow>
                <DetailLabel>
                  <MapPin />
                  Address:
                </DetailLabel>
                <DetailValue>
                  {formatStructuredAddress(bench.reverse_geocode)}
                </DetailValue>
              </DetailRow>
            )}
          </BenchDetails>

          {/* Debug Information */}
          <DebugDetails $show={state.debugMode}>
            <DetailRow>
              <DetailLabel>Source:</DetailLabel>
              <DetailValue
                style={{
                  textTransform: "uppercase",
                  fontWeight: 600,
                  color: getDetectionTypeColor(bench.detection_type),
                }}
              >
                {getSourceDisplayName(bench.source)}
              </DetailValue>
            </DetailRow>
            <DetailRow>
              <DetailLabel>Best Confidence:</DetailLabel>
              <DetailValue>
                {(bench.best_confidence * 100).toFixed(1)}% (
                {bench.detection_type})
              </DetailValue>
            </DetailRow>
            <ConfidenceBar
              $confidence={bench.best_confidence}
              $type={bench.detection_type}
            />

            {(bench.roboflow_confidence || 0) > 0 && (
              <>
                <DetailRow>
                  <DetailLabel>Roboflow:</DetailLabel>
                  <DetailValue>
                    {((bench.roboflow_confidence || 0) * 100).toFixed(1)}%
                  </DetailValue>
                </DetailRow>
                <ConfidenceBar
                  $confidence={bench.roboflow_confidence || 0}
                  $type="roboflow"
                />
              </>
            )}

            {(bench.ultralytics_confidence || 0) > 0 && (
              <>
                <DetailRow>
                  <DetailLabel>Ultralytics:</DetailLabel>
                  <DetailValue>
                    {((bench.ultralytics_confidence || 0) * 100).toFixed(1)}%
                  </DetailValue>
                </DetailRow>
                <ConfidenceBar
                  $confidence={bench.ultralytics_confidence || 0}
                  $type="ultralytics"
                />
              </>
            )}

            {(bench.mapillary_confidence || 0) > 0 && (
              <>
                <DetailRow>
                  <DetailLabel>Mapillary:</DetailLabel>
                  <DetailValue>
                    {((bench.mapillary_confidence || 0) * 100).toFixed(1)}%
                  </DetailValue>
                </DetailRow>
                <ConfidenceBar
                  $confidence={bench.mapillary_confidence || 0}
                  $type="mapillary"
                />
              </>
            )}
          </DebugDetails>

          {/* Tags */}
          {tags.length > 0 && (
            <Tags>
              {tags.map((tag, index) => (
                <Tag key={index}>{tag}</Tag>
              ))}
            </Tags>
          )}
        </CardContent>
      </CardContainer>

      <ReportModal
        bench={bench}
        imageUrl={imageUrl || undefined}
        imageId={imageId || undefined}
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
      />
    </GlobalMiniMapStyles>
  )
}

export default BenchCard
