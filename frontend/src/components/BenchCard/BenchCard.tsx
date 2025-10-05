import { motion } from "framer-motion"
import { Camera, Hash, MapPin, Target } from "lucide-react"
import type React from "react"
import { useRef, useState } from "react"
import styled, { keyframes } from "styled-components"
import { useApp } from "../../contexts/AppContext"
import type { Bench } from "../../types"

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
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  overflow: hidden;
  box-shadow: ${({ theme }) => theme.shadows.sm};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  transition: all ${({ theme }) => theme.transitions.normal};
  animation: ${fadeInUp} 0.4s ${({ theme }) => theme.easing.easeOut} forwards;
  opacity: 0;

  &:hover {
    transform: translateY(-2px);
    box-shadow: ${({ theme }) => theme.shadows.lg};
  }
`

const ImageContainer = styled.div`
  position: relative;
  height: 200px;
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
  background: ${({ theme }) => theme.colors.overlay};
  opacity: 0;
  transition: opacity ${({ theme }) => theme.transitions.normal};
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  text-align: center;
  pointer-events: none;

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
  
  ${({ $variant, theme }) => {
    switch ($variant) {
      case "confidence":
        return `
          top: ${theme.spacing[4]};
          right: ${theme.spacing[4]};
          background: ${theme.colors.success};
          color: white;
        `
      case "distance":
        return `
          top: ${theme.spacing[4]};
          left: ${theme.spacing[4]};
          background: rgba(255, 255, 255, 0.9);
          color: ${theme.colors.textPrimary};
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
          top: ${theme.spacing[12]};
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
  padding: ${({ theme }) => theme.spacing[5]};
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
`

interface BenchCardProps {
  bench: Bench
  onImageClick?: (bench: Bench, imageUrl: string, imageId: number) => void
  onStreetViewClick?: (lat: number, lng: number) => void
  animationDelay?: number
}

export const BenchCard: React.FC<BenchCardProps> = ({
  bench,
  onImageClick,
  onStreetViewClick,
  animationDelay = 0,
}) => {
  const { state } = useApp()
  const [_hoverMapLoaded, setHoverMapLoaded] = useState(false)
  const mapRef = useRef<HTMLDivElement>(null)

  // Get primary image
  const imageUrl = bench.image_filenames[0]
    ? `/images/${bench.image_filenames[0]}`
    : null
  const imageId = bench.image_ids[0] || null

  // Format tags (exclude amenity tag)
  const tags = Object.entries(bench.tags)
    .filter(([key]) => key !== "amenity")
    .map(([key, value]) => `${key}: ${value}`)

  // Determine detection type color
  const getDetectionTypeColor = (type: string) => {
    switch (type) {
      case "ultralytics":
        return "#059669"
      case "roboflow":
        return "#2563eb"
      case "mapillary":
        return "#ea580c"
      default:
        return "#6b7280"
    }
  }

  const handleImageClick = () => {
    if (imageUrl && imageId && onImageClick) {
      onImageClick(bench, imageUrl, imageId)
    }
  }

  const handleTitleClick = () => {
    if (onStreetViewClick) {
      onStreetViewClick(bench.lat, bench.lng)
    }
  }

  const handleMouseEnter = () => {
    // Load hover map functionality could be implemented here
    setHoverMapLoaded(true)
  }

  const cardVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.4,
        delay: animationDelay,
        ease: [0.4, 0, 0.2, 1],
      },
    },
  }

  return (
    <CardContainer
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      onMouseEnter={handleMouseEnter}
    >
      <ImageContainer onClick={handleImageClick}>
        {imageUrl ? (
          <BenchImage src={imageUrl} alt={`Bench ${bench.id}`} loading="lazy" />
        ) : (
          <PlaceholderImage>🪑</PlaceholderImage>
        )}

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
          {bench.source}
        </DebugBadge>

        {/* Segmentation Badge */}
        {bench.has_segmentation && (
          <DebugBadge $variant="segmentation" $show={state.debugMode}>
            🎯 SEG
          </DebugBadge>
        )}

        {/* Hover Map */}
        <HoverMap ref={mapRef}>
          {/* Mini map would be rendered here */}
          <div
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "12px",
              color: "#64748b",
            }}
          >
            📍 Map Preview
          </div>
        </HoverMap>
      </ImageContainer>

      <CardContent>
        <BenchTitle onClick={handleTitleClick}>
          <MapPin />
          Bench #{bench.id}
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
          <DetailRow>
            <DetailLabel>
              <Camera />
              Images:
            </DetailLabel>
            <DetailValue>{bench.image_count}</DetailValue>
          </DetailRow>
        </BenchDetails>

        {/* Debug Information */}
        <DebugDetails $show={state.debugMode}>
          <DetailRow>
            <DetailLabel>Source:</DetailLabel>
            <DetailValue
              style={{
                textTransform: "uppercase",
                fontWeight: 600,
                color: getDetectionTypeColor(bench.source),
              }}
            >
              {bench.source}
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

          {bench.roboflow_confidence > 0 && (
            <>
              <DetailRow>
                <DetailLabel>Roboflow:</DetailLabel>
                <DetailValue>
                  {(bench.roboflow_confidence * 100).toFixed(1)}%
                </DetailValue>
              </DetailRow>
              <ConfidenceBar
                $confidence={bench.roboflow_confidence}
                $type="roboflow"
              />
            </>
          )}

          {bench.ultralytics_confidence > 0 && (
            <>
              <DetailRow>
                <DetailLabel>Ultralytics:</DetailLabel>
                <DetailValue>
                  {(bench.ultralytics_confidence * 100).toFixed(1)}%
                </DetailValue>
              </DetailRow>
              <ConfidenceBar
                $confidence={bench.ultralytics_confidence}
                $type="ultralytics"
              />
            </>
          )}

          {bench.mapillary_confidence > 0 && (
            <>
              <DetailRow>
                <DetailLabel>Mapillary:</DetailLabel>
                <DetailValue>
                  {(bench.mapillary_confidence * 100).toFixed(1)}%
                </DetailValue>
              </DetailRow>
              <ConfidenceBar
                $confidence={bench.mapillary_confidence}
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
  )
}

export default BenchCard
