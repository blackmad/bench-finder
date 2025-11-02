import { useQuery } from "@tanstack/react-query"
import L from "leaflet"
import {
  ArrowLeft,
  Camera,
  ExternalLink,
  Flag,
  Hash,
  MapPin,
  Target,
} from "lucide-react"
import type React from "react"
import { useEffect, useState } from "react"
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet"
import { Link, useNavigate, useParams } from "react-router-dom"
import styled from "styled-components"
import "leaflet/dist/leaflet.css"
import "../utils/leafletFix"
import type { StructuredAddress, WebBenchData } from "../api"
import { DataSource } from "../api"
import Header from "../components/Header/Header"

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

import DetectionData from "../components/DetectionData/DetectionData"
import LoadingSpinner from "../components/LoadingSpinner/LoadingSpinner"
import Modal from "../components/Modal/Modal"
import ReportModal from "../components/ReportModal/ReportModal"
import { benchApi } from "../services/api"

const PageContainer = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: ${({ theme }) => theme.colors.backgroundSecondary};
`

const ContentContainer = styled.div`
  flex: 1;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: ${({ theme }) => theme.spacing[8]} ${({ theme }) => theme.spacing[5]};

  @media (max-width: 640px) {
    padding: ${({ theme }) => theme.spacing[6]} ${({ theme }) => theme.spacing[4]};
  }
`

const BackLink = styled(Link)`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  color: ${({ theme }) => theme.colors.textSecondary};
  text-decoration: none;
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  margin-bottom: ${({ theme }) => theme.spacing[6]};
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }

  svg {
    width: 18px;
    height: 18px;
  }
`

const DetailCard = styled.div`
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  padding: ${({ theme }) => theme.spacing[8]};
  box-shadow: ${({ theme }) => theme.shadows.md};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  margin-bottom: ${({ theme }) => theme.spacing[6]};

  @media (max-width: 640px) {
    padding: ${({ theme }) => theme.spacing[6]};
  }
`

const Title = styled.h1`
  font-size: ${({ theme }) => theme.typography.sizes["3xl"]};
  font-weight: ${({ theme }) => theme.typography.weights.bold};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin: 0 0 ${({ theme }) => theme.spacing[6]} 0;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[4]};
  flex-wrap: wrap;

  @media (max-width: 640px) {
    font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
  }
`

const ImageGallery = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: ${({ theme }) => theme.spacing[4]};
  margin-bottom: ${({ theme }) => theme.spacing[6]};

  @media (max-width: 640px) {
    grid-template-columns: 1fr;
  }
`

const ImageContainer = styled.div<{ $isBestImage?: boolean }>`
  position: relative;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  overflow: hidden;
  cursor: pointer;
  transition: transform ${({ theme }) => theme.transitions.fast};
  border: ${({ $isBestImage, theme }) =>
    $isBestImage ? `3px solid ${theme.colors.success}` : "none"};
  box-shadow: ${({ $isBestImage, theme }) =>
    $isBestImage
      ? `0 0 0 2px ${theme.colors.success}40, ${theme.shadows.md}`
      : "none"};

  &:hover {
    transform: scale(1.02);
  }

  &::after {
    content: ${({ $isBestImage }) => ($isBestImage ? '"⭐ Best Image"' : "none")};
    position: absolute;
    top: ${({ theme }) => theme.spacing[2]};
    right: ${({ theme }) => theme.spacing[2]};
    background: ${({ theme }) => theme.colors.success};
    color: white;
    padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[2]};
    border-radius: ${({ theme }) => theme.borderRadius.md};
    font-size: ${({ theme }) => theme.typography.sizes.xs};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
    z-index: 10;
    pointer-events: none;
  }
`

const GalleryImage = styled.img`
  width: 100%;
  height: 200px;
  object-fit: cover;
  display: block;
`

// Global styles for bench marker
const GlobalMapStyles = styled.div`
  .bench-detail-marker {
    background: none !important;
    border: none !important;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    line-height: 1;
  }
`

const Section = styled.section`
  margin-bottom: ${({ theme }) => theme.spacing[6]};

  &:last-child {
    margin-bottom: 0;
  }
`

const SectionTitle = styled.h2`
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};

  svg {
    width: 20px;
    height: 20px;
  }
`

const InfoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: ${({ theme }) => theme.spacing[4]};
  margin-bottom: ${({ theme }) => theme.spacing[6]};
`

const InfoItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[1]};
`

const InfoLabel = styled.label`
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  color: ${({ theme }) => theme.colors.textSecondary};
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};

  svg {
    width: 14px;
    height: 14px;
  }
`

const InfoValue = styled.div`
  font-size: ${({ theme }) => theme.typography.sizes.base};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.typography.fonts.mono};
  word-break: break-all;
`

const Badge = styled.span<{ $variant: string }>`
  display: inline-block;
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[3]};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  text-transform: uppercase;

  ${({ $variant, theme }) => {
    switch ($variant) {
      case "detected":
        return `
          background: ${theme.colors.success};
          color: white;
        `
      case "no_bench":
        return `
          background: ${theme.colors.error};
          color: white;
        `
      case "osm":
        return `
          background: ${theme.colors.gray600};
          color: white;
        `
      case "mapillary":
        return `
          background: ${theme.colors.mapillary};
          color: white;
        `
      default:
        return `
          background: ${theme.colors.gray200};
          color: ${theme.colors.textPrimary};
        `
    }
  }}
`

const TagsContainer = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing[2]};
  margin-bottom: ${({ theme }) => theme.spacing[6]};
`

const Tag = styled.span`
  display: inline-block;
  background: ${({ theme }) => theme.colors.gray100};
  color: ${({ theme }) => theme.colors.gray700};
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[3]};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
`

const ActionButtons = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[4]};
  flex-wrap: wrap;
  margin-top: ${({ theme }) => theme.spacing[6]};
`

const ActionButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[5]};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.textPrimary};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};

  &:hover {
    background: ${({ theme }) => theme.colors.gray50};
    border-color: ${({ theme }) => theme.colors.primary};
    color: ${({ theme }) => theme.colors.primary};
  }

  svg {
    width: 18px;
    height: 18px;
  }
`

const ReportActionButton = styled(ActionButton)`
  border-color: ${({ theme }) => theme.colors.warning};
  color: ${({ theme }) => theme.colors.warning};

  &:hover {
    background: ${({ theme }) => theme.colors.warning}20;
    border-color: ${({ theme }) => theme.colors.warning};
    color: ${({ theme }) => theme.colors.warning};
  }
`

const ErrorContainer = styled.div`
  text-align: center;
  padding: ${({ theme }) => theme.spacing[16]} ${({ theme }) => theme.spacing[5]};
  color: ${({ theme }) => theme.colors.textSecondary};

  h2 {
    font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
    color: ${({ theme }) => theme.colors.textPrimary};
    margin-bottom: ${({ theme }) => theme.spacing[4]};
  }

  p {
    margin-bottom: ${({ theme }) => theme.spacing[6]};
  }
`

const ConfidenceBar = styled.div<{ $confidence: number; $type: string }>`
  width: 100%;
  height: 6px;
  background: ${({ theme }) => theme.colors.gray200};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  overflow: hidden;
  margin-top: ${({ theme }) => theme.spacing[2]};

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

const MapSection = styled.div`
  margin-bottom: ${({ theme }) => theme.spacing[6]};
`

const MapContainerStyled = styled.div`
  width: 100%;
  height: 400px;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  overflow: hidden;
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  box-shadow: ${({ theme }) => theme.shadows.sm};
  background: ${({ theme }) => theme.colors.gray100};

  .leaflet-container {
    height: 100%;
    width: 100%;
    border-radius: ${({ theme }) => theme.borderRadius.lg};
  }
`

// Component to update map center when bench location changes
const MapCenterUpdater: React.FC<{
  center: [number, number]
  zoom: number
}> = ({ center, zoom }) => {
  const map = useMap()

  useEffect(() => {
    map.setView(center, zoom)
  }, [map, center, zoom])

  return null
}

const BenchDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null)
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [currentModalIndex, setCurrentModalIndex] = useState(0)
  const [isReportModalOpen, setIsReportModalOpen] = useState(false)

  const benchId = id ? parseInt(id, 10) : null

  const {
    data: bench,
    isLoading,
    error,
    refetch,
  } = useQuery<WebBenchData>({
    queryKey: ["bench", benchId],
    queryFn: () => benchApi.getBenchById(benchId!, true), // Include detection data
    enabled: benchId !== null && !Number.isNaN(benchId),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })

  if (benchId === null || Number.isNaN(benchId)) {
    return (
      <PageContainer>
        <Header />
        <ContentContainer>
          <ErrorContainer>
            <h2>Invalid Bench ID</h2>
            <p>The bench ID in the URL is invalid.</p>
            <ActionButton onClick={() => navigate("/cards")}>
              <ArrowLeft />
              Back to Benches
            </ActionButton>
          </ErrorContainer>
        </ContentContainer>
      </PageContainer>
    )
  }

  if (isLoading) {
    return (
      <PageContainer>
        <Header />
        <ContentContainer>
          <LoadingSpinner />
        </ContentContainer>
      </PageContainer>
    )
  }

  if (error || !bench) {
    return (
      <PageContainer>
        <Header />
        <ContentContainer>
          <ErrorContainer>
            <h2>Bench Not Found</h2>
            <p>
              The bench with ID {benchId} could not be found. It may have been
              deleted or the ID may be incorrect.
            </p>
            <ActionButtons>
              <ActionButton onClick={() => refetch()}>Try Again</ActionButton>
              <ActionButton onClick={() => navigate("/cards")}>
                <ArrowLeft />
                Back to Benches
              </ActionButton>
            </ActionButtons>
          </ErrorContainer>
        </ContentContainer>
      </PageContainer>
    )
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

  // Format tags (exclude amenity tag and null values)
  const tags = Object.entries(bench.tags || {})
    .filter(
      ([key, value]) => key !== "amenity" && value != null && value !== "null"
    )
    .map(([key, value]) => ({ key, value }))

  const handleImageClick = (
    imageUrl: string,
    imageId: number,
    index: number
  ) => {
    setSelectedImageUrl(imageUrl)
    setSelectedImageId(imageId)
    setCurrentModalIndex(index)
    setModalOpen(true)
  }

  const handlePrevImage = () => {
    if (!bench.image_filenames || bench.image_filenames.length === 0) return
    const newIndex =
      (currentModalIndex - 1 + bench.image_filenames.length) %
      bench.image_filenames.length
    const newImageId = bench.image_ids?.[newIndex] || null
    const newUrl =
      bench.image_urls?.[newIndex] ??
      (bench.image_filenames[newIndex]
        ? `/images/${bench.image_filenames[newIndex]}`
        : null)
    if (newUrl) {
      setSelectedImageUrl(newUrl)
      setSelectedImageId(newImageId)
      setCurrentModalIndex(newIndex)
    }
  }

  const handleNextImage = () => {
    if (!bench.image_filenames || bench.image_filenames.length === 0) return
    const newIndex = (currentModalIndex + 1) % bench.image_filenames.length
    const newImageId = bench.image_ids?.[newIndex] || null
    const newUrl =
      bench.image_urls?.[newIndex] ??
      (bench.image_filenames[newIndex]
        ? `/images/${bench.image_filenames[newIndex]}`
        : null)
    if (newUrl) {
      setSelectedImageUrl(newUrl)
      setSelectedImageId(newImageId)
      setCurrentModalIndex(newIndex)
    }
  }

  const handleNavigateImage = (direction: "prev" | "next") => {
    // Navigate between images of the same bench
    if (direction === "prev") {
      handlePrevImage()
    } else {
      handleNextImage()
    }
  }

  const handleImageSelect = (imageUrl: string, imageId: number) => {
    setSelectedImageUrl(imageUrl)
    setSelectedImageId(imageId)
    // Find the index of the selected image
    const index = bench.image_ids?.indexOf(imageId) ?? 0
    setCurrentModalIndex(index)
  }

  // Create array of image data for navigation (needed for Modal's navigation logic)
  const imageDataForNavigation = bench
    ? bench.image_filenames.map((filename, index) => ({
        ...bench,
        image_filenames: [filename],
        image_ids: [bench.image_ids?.[index] || 0],
      }))
    : []

  const handleOpenStreetMap = () => {
    const url = `https://www.openstreetmap.org/?mlat=${bench.lat}&mlon=${bench.lng}&zoom=18`
    window.open(url, "_blank")
  }

  const handleGoogleMaps = () => {
    const url = `https://www.google.com/maps?q=${bench.lat},${bench.lng}`
    window.open(url, "_blank")
  }

  const imageUrl =
    bench.image_urls?.[0] ??
    (bench.image_filenames?.[0] ? `/images/${bench.image_filenames[0]}` : null)
  const imageId = bench.image_ids?.[0] || null

  return (
    <GlobalMapStyles>
      <PageContainer>
        <Header />
        <ContentContainer>
          <BackLink to="/cards">
            <ArrowLeft />
            Back to all benches
          </BackLink>

          <DetailCard>
            <Title>
              Bench #{bench.id}
              <Badge $variant={bench.bench_found ? "detected" : "no_bench"}>
                {bench.bench_found ? "✅ Bench Detected" : "❌ No Bench"}
              </Badge>
              <Badge
                $variant={bench.source === DataSource.OSM ? "osm" : "mapillary"}
              >
                {getSourceDisplayName(bench.source)}
              </Badge>
            </Title>

            {/* Image Gallery */}
            {bench.image_filenames && bench.image_filenames.length > 0 && (
              <Section>
                <SectionTitle>
                  <Camera />
                  Images ({bench.image_count})
                </SectionTitle>
                <ImageGallery>
                  {bench.image_filenames.map((filename, index) => {
                    const imgId = bench.image_ids?.[index] || null
                    const imgUrl =
                      bench.image_urls?.[index] ?? `/images/${filename}`
                    return (
                      <ImageContainer
                        key={index}
                        onClick={() =>
                          handleImageClick(imgUrl, imgId || 0, index)
                        }
                      >
                        <GalleryImage
                          src={imgUrl}
                          alt={`Bench ${bench.id} - Image ${index + 1}`}
                          loading="lazy"
                        />
                      </ImageContainer>
                    )
                  })}
                </ImageGallery>
              </Section>
            )}

            {/* Map */}
            <MapSection>
              <SectionTitle>
                <MapPin />
                Location Map
              </SectionTitle>
              <MapContainerStyled>
                <MapContainer
                  center={[bench.lat, bench.lng]}
                  zoom={16}
                  style={{ height: "100%", width: "100%" }}
                  zoomControl={true}
                  scrollWheelZoom={true}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    maxZoom={19}
                  />
                  <MapCenterUpdater center={[bench.lat, bench.lng]} zoom={16} />
                  <Marker
                    position={[bench.lat, bench.lng]}
                    icon={L.divIcon({
                      html: "🪑",
                      className: "bench-detail-marker",
                      iconSize: [30, 30],
                      iconAnchor: [15, 15],
                    })}
                  />
                </MapContainer>
              </MapContainerStyled>
            </MapSection>

            {/* Basic Information */}
            <Section>
              <SectionTitle>
                <Target />
                Location Information
              </SectionTitle>
              <InfoGrid>
                <InfoItem>
                  <InfoLabel>
                    <MapPin />
                    Coordinates
                  </InfoLabel>
                  <InfoValue>
                    {bench.lat.toFixed(6)}, {bench.lng.toFixed(6)}
                  </InfoValue>
                </InfoItem>
                {bench.reverse_geocode && (
                  <InfoItem>
                    <InfoLabel>
                      <MapPin />
                      Address
                    </InfoLabel>
                    <InfoValue>
                      {formatStructuredAddress(bench.reverse_geocode)}
                    </InfoValue>
                  </InfoItem>
                )}
                <InfoItem>
                  <InfoLabel>
                    <Hash />
                    Provider ID
                  </InfoLabel>
                  <InfoValue>{bench.provider_id || "N/A"}</InfoValue>
                </InfoItem>
                <InfoItem>
                  <InfoLabel>
                    <Camera />
                    Image Count
                  </InfoLabel>
                  <InfoValue>{bench.image_count}</InfoValue>
                </InfoItem>
                <InfoItem>
                  <InfoLabel>Detection Status</InfoLabel>
                  <InfoValue>
                    {bench.bench_found ? "Bench detected" : "No bench detected"}
                  </InfoValue>
                </InfoItem>
              </InfoGrid>
            </Section>

            {/* Detection Confidence */}
            <Section>
              <SectionTitle>Detection Confidence</SectionTitle>
              <InfoGrid>
                <InfoItem>
                  <InfoLabel>
                    Best Confidence ({bench.detection_type})
                  </InfoLabel>
                  <InfoValue>
                    {(bench.best_confidence * 100).toFixed(1)}%
                  </InfoValue>
                  <ConfidenceBar
                    $confidence={bench.best_confidence}
                    $type={bench.detection_type}
                  />
                </InfoItem>
                {bench.ultralytics_confidence &&
                  bench.ultralytics_confidence > 0 && (
                    <InfoItem>
                      <InfoLabel>Ultralytics</InfoLabel>
                      <InfoValue>
                        {(bench.ultralytics_confidence * 100).toFixed(1)}%
                      </InfoValue>
                      <ConfidenceBar
                        $confidence={bench.ultralytics_confidence}
                        $type="ultralytics"
                      />
                    </InfoItem>
                  )}
                {bench.roboflow_confidence && bench.roboflow_confidence > 0 && (
                  <InfoItem>
                    <InfoLabel>Roboflow</InfoLabel>
                    <InfoValue>
                      {(bench.roboflow_confidence * 100).toFixed(1)}%
                    </InfoValue>
                    <ConfidenceBar
                      $confidence={bench.roboflow_confidence}
                      $type="roboflow"
                    />
                  </InfoItem>
                )}
                {bench.mapillary_confidence &&
                  bench.mapillary_confidence > 0 && (
                    <InfoItem>
                      <InfoLabel>Mapillary</InfoLabel>
                      <InfoValue>
                        {(bench.mapillary_confidence * 100).toFixed(1)}%
                      </InfoValue>
                      <ConfidenceBar
                        $confidence={bench.mapillary_confidence}
                        $type="mapillary"
                      />
                    </InfoItem>
                  )}
              </InfoGrid>
              {bench.has_segmentation && (
                <Badge $variant="default" style={{ marginTop: "16px" }}>
                  🎯 Has Segmentation Data
                </Badge>
              )}
            </Section>

            {/* Detection Data */}
            {bench.detection_items && bench.detection_items.length > 0 && (
              <Section>
                <SectionTitle>Detection Details</SectionTitle>
                <DetectionData
                  detectionItems={bench.detection_items}
                  detectionSource={bench.detection_type}
                />
              </Section>
            )}

            {/* Tags */}
            {tags.length > 0 && (
              <Section>
                <SectionTitle>Tags</SectionTitle>
                <TagsContainer>
                  {tags.map((tag, index) => (
                    <Tag key={index}>
                      {tag.key}: {String(tag.value)}
                    </Tag>
                  ))}
                </TagsContainer>
              </Section>
            )}

            {/* Action Buttons */}
            <ActionButtons>
              <ActionButton onClick={handleOpenStreetMap}>
                <ExternalLink />
                View on OpenStreetMap
              </ActionButton>
              <ActionButton onClick={handleGoogleMaps}>
                <ExternalLink />
                View on Google Maps
              </ActionButton>
              <ReportActionButton onClick={() => setIsReportModalOpen(true)}>
                <Flag />
                Report Issue
              </ReportActionButton>
            </ActionButtons>
          </DetailCard>
        </ContentContainer>

        {/* Image Modal with Segmentation */}
        {modalOpen && bench && selectedImageUrl && (
          <Modal
            isOpen={modalOpen}
            onClose={() => setModalOpen(false)}
            bench={bench}
            imageUrl={selectedImageUrl}
            imageId={selectedImageId}
            currentIndex={currentModalIndex}
            // Pass array of benches with individual images to enable navigation
            allBenches={imageDataForNavigation}
            onNavigate={
              bench.image_filenames && bench.image_filenames.length > 1
                ? handleNavigateImage
                : undefined
            }
            onReport={() => setIsReportModalOpen(true)}
            onImageSelect={handleImageSelect}
          />
        )}

        {/* Report Modal */}
        <ReportModal
          bench={bench}
          imageUrl={imageUrl || undefined}
          imageId={imageId || undefined}
          isOpen={isReportModalOpen}
          onClose={() => setIsReportModalOpen(false)}
        />
      </PageContainer>
    </GlobalMapStyles>
  )
}

export default BenchDetailPage
