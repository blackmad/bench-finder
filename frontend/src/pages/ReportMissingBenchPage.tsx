import { motion } from "framer-motion"
import L from "leaflet"
import {
  AlertCircle,
  ArrowLeft,
  Camera,
  Check,
  Crosshair,
  Image as ImageIcon,
  Map as MapIcon,
  MapPin,
  Send,
} from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet"
import { useNavigate } from "react-router-dom"
import styled from "styled-components"
import { LocationMethod } from "../api"
import { benchApi } from "../services/api"
import {
  captureImage,
  getCurrentLocation,
  type ImageCaptureResult,
} from "../utils/imageCapture"
import "../utils/leafletFix"

const PageContainer = styled.div`
  min-height: 100vh;
  background: ${({ theme }) => theme.colors.background};
  display: flex;
  flex-direction: column;
`

const Header = styled.header`
  background: ${({ theme }) => theme.colors.background};
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
  padding: ${({ theme }) => theme.spacing[4]} ${({ theme }) => theme.spacing[4]};
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[3]};
  position: sticky;
  top: 0;
  z-index: 100;
`

const BackButton = styled.button`
  background: none;
  border: none;
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
  padding: ${({ theme }) => theme.spacing[2]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ theme }) => theme.colors.gray100};
  }
`

const Title = styled.h1`
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin: 0;
  flex: 1;
`

const Content = styled.main`
  flex: 1;
  display: flex;
  flex-direction: column;
`

const ModeSelector = styled.div`
  padding: ${({ theme }) => theme.spacing[4]};
  background: ${({ theme }) => theme.colors.gray50};
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const ModeButtons = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: ${({ theme }) => theme.spacing[3]};
  margin-bottom: ${({ theme }) => theme.spacing[4]};

  @media (max-width: 480px) {
    grid-template-columns: 1fr;
    gap: ${({ theme }) => theme.spacing[2]};
  }
`

const ModeButton = styled.button<{ $active: boolean }>`
  padding: ${({ theme }) => theme.spacing[4]};
  border: 2px solid ${({ $active, theme }) => ($active ? theme.colors.primary : theme.colors.borderLight)};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  background: ${({ $active, theme }) => ($active ? theme.colors.primary : theme.colors.background)};
  color: ${({ $active, theme }) => ($active ? "white" : theme.colors.textPrimary)};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  text-align: center;

  &:hover:not(:disabled) {
    border-color: ${({ theme }) => theme.colors.primary};
    background: ${({ $active, theme }) => ($active ? theme.colors.primaryHover : theme.colors.gray50)};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  svg {
    width: 32px;
    height: 32px;
  }

  h3 {
    margin: 0;
    font-size: ${({ theme }) => theme.typography.sizes.base};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
  }

  p {
    margin: 0;
    font-size: ${({ theme }) => theme.typography.sizes.sm};
    opacity: 0.9;
  }
`

const StatusMessage = styled.div<{ $type: "info" | "success" | "error" }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  font-size: ${({ theme }) => theme.typography.sizes.sm};

  ${({ $type, theme }) => {
    switch ($type) {
      case "success":
        return `
          background: ${theme.colors.successLight || "#d1fae5"};
          color: ${theme.colors.success};
          border: 1px solid ${theme.colors.success};
        `
      case "error":
        return `
          background: ${theme.colors.errorLight || "#fef2f2"};
          color: ${theme.colors.error};
          border: 1px solid ${theme.colors.error};
        `
      default:
        return `
          background: ${theme.colors.infoLight || "#eff6ff"};
          color: ${theme.colors.info || theme.colors.primary};
          border: 1px solid ${theme.colors.primary};
        `
    }
  }}

  svg {
    width: 16px;
    height: 16px;
  }
`

const MapSection = styled.div`
  flex: 1;
  position: relative;
  min-height: 300px;

  .leaflet-container {
    height: 100%;
    width: 100%;
  }
`

const MapInstructions = styled.div`
  position: absolute;
  top: ${({ theme }) => theme.spacing[4]};
  left: ${({ theme }) => theme.spacing[4]};
  right: ${({ theme }) => theme.spacing[4]};
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(4px);
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  box-shadow: ${({ theme }) => theme.shadows.sm};
  z-index: 1000;
  text-align: center;

  p {
    margin: 0;
    color: ${({ theme }) => theme.colors.textSecondary};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
  }
`

const FormSection = styled.div`
  padding: ${({ theme }) => theme.spacing[4]};
  border-top: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const FormGroup = styled.div`
  margin-bottom: ${({ theme }) => theme.spacing[4]};
`

const Label = styled.label`
  display: block;
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin-bottom: ${({ theme }) => theme.spacing[2]};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
`

const Textarea = styled.textarea`
  width: 100%;
  min-height: 80px;
  padding: ${({ theme }) => theme.spacing[3]};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: inherit;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: ${({ theme }) => theme.colors.background};
  resize: vertical;
  transition: border-color ${({ theme }) => theme.transitions.fast};

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
  }

  &::placeholder {
    color: ${({ theme }) => theme.colors.textTertiary};
  }
`

const PhotoSection = styled.div`
  border: 2px dashed ${({ theme }) => theme.colors.borderLight};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[4]};
  text-align: center;
  margin-bottom: ${({ theme }) => theme.spacing[4]};

  img {
    max-width: 100%;
    max-height: 200px;
    border-radius: ${({ theme }) => theme.borderRadius.md};
    margin-bottom: ${({ theme }) => theme.spacing[2]};
  }
`

const PhotoButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[4]};
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.borderRadius.md};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};

  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.primaryHover};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const SubmitButton = styled.button<{ $variant?: "primary" | "secondary" }>`
  width: 100%;
  padding: ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  font-size: ${({ theme }) => theme.typography.sizes.base};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  display: flex;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing[2]};

  ${({ $variant = "primary", theme }) =>
    $variant === "primary"
      ? `
        background: ${theme.colors.primary};
        color: white;
        border: 1px solid ${theme.colors.primary};

        &:hover:not(:disabled) {
          background: ${theme.colors.primaryHover};
          border-color: ${theme.colors.primaryHover};
        }
      `
      : `
        background: ${theme.colors.background};
        color: ${theme.colors.textSecondary};
        border: 1px solid ${theme.colors.borderLight};

        &:hover:not(:disabled) {
          color: ${theme.colors.textPrimary};
          border-color: ${theme.colors.gray300};
        }
      `}

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const SuccessScreen = styled(motion.div)`
  padding: ${({ theme }) => theme.spacing[8]} ${({ theme }) => theme.spacing[4]};
  text-align: center;
  color: ${({ theme }) => theme.colors.success};

  svg {
    width: 64px;
    height: 64px;
    margin-bottom: ${({ theme }) => theme.spacing[4]};
  }

  h2 {
    font-size: ${({ theme }) => theme.typography.sizes["2xl"]};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
  }

  p {
    margin: 0 0 ${({ theme }) => theme.spacing[6]} 0;
    color: ${({ theme }) => theme.colors.textSecondary};
    font-size: ${({ theme }) => theme.typography.sizes.base};
  }
`

type Mode = "gps" | "map"

interface Location {
  lat: number
  lng: number
  accuracy?: number
}

// Map click handler component
function MapClickHandler({
  onLocationSelect,
}: {
  onLocationSelect: (location: Location) => void
}) {
  useMapEvents({
    click: (e) => {
      onLocationSelect({
        lat: e.latlng.lat,
        lng: e.latlng.lng,
      })
    },
  })
  return null
}

const ReportMissingBenchPage: React.FC = () => {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>("gps")
  const [location, setLocation] = useState<Location | null>(null)
  const [userLocation, setUserLocation] = useState<Location | null>(null)
  const [description, setDescription] = useState("")
  const [capturedImage, setCapturedImage] = useState<ImageCaptureResult | null>(
    null
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{
    type: "info" | "success" | "error"
    text: string
  } | null>(null)
  const [isGettingLocation, setIsGettingLocation] = useState(false)
  const mapRef = useRef<L.Map | null>(null)
  const descriptionId = useId()

  // Get user's current location on mount
  useEffect(() => {
    const getUserLocation = async () => {
      try {
        const pos = await getCurrentLocation()
        setUserLocation(pos)
        if (mode === "gps" && !location) {
          setLocation(pos)
        }
      } catch (error) {
        console.warn("Failed to get user location:", error)
      }
    }

    getUserLocation()
  }, [location, mode])

  const handleModeChange = async (newMode: Mode) => {
    setMode(newMode)
    setStatusMessage(null)

    if (newMode === "gps") {
      if (userLocation) {
        setLocation(userLocation)
      } else {
        setIsGettingLocation(true)
        try {
          const pos = await getCurrentLocation()
          setUserLocation(pos)
          setLocation(pos)
          setStatusMessage({
            type: "success",
            text: `Location found with ${pos.accuracy}m accuracy`,
          })
        } catch (_error) {
          setStatusMessage({
            type: "error",
            text: "Failed to get your location. Please enable GPS and try again.",
          })
        } finally {
          setIsGettingLocation(false)
        }
      }
    } else {
      setLocation(null)
    }
  }

  const handleCaptureImage = async () => {
    try {
      const result = await captureImage({
        preferCamera: true,
        maxWidth: 1920,
        maxHeight: 1920,
        quality: 0.8,
      })
      setCapturedImage(result)
      setStatusMessage({
        type: "success",
        text: "Photo captured successfully!",
      })
    } catch (_error) {
      setStatusMessage({
        type: "error",
        text: "Failed to capture photo. Please try again.",
      })
    }
  }

  const handleSubmit = async () => {
    if (!location || isSubmitting) return

    setIsSubmitting(true)
    setStatusMessage(null)

    try {
      await benchApi.reportMissingBench({
        lat: location.lat,
        lng: location.lng,
        description: description || undefined,
        locationMethod:
          mode === "gps" ? LocationMethod.GPS : LocationMethod.MAP_CLICK,
        userLocationLat: userLocation?.lat,
        userLocationLng: userLocation?.lng,
        accuracyMeters: location.accuracy,
        imageData: capturedImage?.dataUrl,
      })

      setIsSuccess(true)
    } catch (error) {
      console.error("Failed to submit report:", error)
      setStatusMessage({
        type: "error",
        text: "Failed to submit report. Please try again.",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSuccess) {
    return (
      <PageContainer>
        <SuccessScreen
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", damping: 25, stiffness: 500 }}
        >
          <Check />
          <h2>Report Submitted!</h2>
          <p>
            Thank you for reporting this missing bench. Our team will review
            your submission and add it to our database if verified.
          </p>
          <SubmitButton onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
            Go Back
          </SubmitButton>
        </SuccessScreen>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <Header>
        <BackButton onClick={() => navigate(-1)}>
          <ArrowLeft size={20} />
        </BackButton>
        <Title>Report Missing Bench</Title>
      </Header>

      <Content>
        <ModeSelector>
          <ModeButtons>
            <ModeButton
              $active={mode === "gps"}
              onClick={() => handleModeChange("gps")}
              disabled={isGettingLocation}
            >
              <Crosshair />
              <h3>RIGHT HERE</h3>
              <p>Use your current GPS location</p>
            </ModeButton>
            <ModeButton
              $active={mode === "map"}
              onClick={() => handleModeChange("map")}
              disabled={isGettingLocation}
            >
              <MapIcon />
              <h3>MAP VIEW</h3>
              <p>Click on the map to select location</p>
            </ModeButton>
          </ModeButtons>

          {statusMessage && (
            <StatusMessage $type={statusMessage.type}>
              {statusMessage.type === "error" ? (
                <AlertCircle size={16} />
              ) : statusMessage.type === "success" ? (
                <Check size={16} />
              ) : (
                <MapPin size={16} />
              )}
              {statusMessage.text}
            </StatusMessage>
          )}
        </ModeSelector>

        {mode === "map" && (
          <MapSection>
            <MapInstructions>
              <p>Tap anywhere on the map to select where you saw a bench</p>
            </MapInstructions>
            <MapContainer
              center={
                userLocation
                  ? [userLocation.lat, userLocation.lng]
                  : [52.3613577, 4.8666322]
              }
              zoom={15}
              style={{ height: "100%", width: "100%" }}
              ref={mapRef}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapClickHandler onLocationSelect={setLocation} />
              {location && <Marker position={[location.lat, location.lng]} />}
              {userLocation && userLocation !== location && (
                <Marker
                  position={[userLocation.lat, userLocation.lng]}
                  icon={L.divIcon({
                    html: "📱",
                    className: "user-location-marker",
                    iconSize: [20, 20],
                    iconAnchor: [10, 10],
                  })}
                />
              )}
            </MapContainer>
          </MapSection>
        )}

        <FormSection>
          <FormGroup>
            <Label htmlFor={descriptionId}>Describe the bench (optional)</Label>
            <Textarea
              id={descriptionId}
              placeholder="e.g., wooden bench facing the pond, metal bench near the playground..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormGroup>

          <FormGroup>
            <Label>Add Photo (optional)</Label>
            <PhotoSection>
              {capturedImage ? (
                <>
                  <img src={capturedImage.dataUrl} alt="Captured bench" />
                  <div>Photo ready to submit</div>
                  <PhotoButton onClick={handleCaptureImage}>
                    <Camera size={16} />
                    Take Another Photo
                  </PhotoButton>
                </>
              ) : (
                <>
                  <ImageIcon size={48} color="#9ca3af" />
                  <p>A photo helps us verify and locate the bench</p>
                  <PhotoButton onClick={handleCaptureImage}>
                    <Camera size={16} />
                    Take Photo
                  </PhotoButton>
                </>
              )}
            </PhotoSection>
          </FormGroup>

          <SubmitButton
            onClick={handleSubmit}
            disabled={!location || isSubmitting}
          >
            {isSubmitting ? (
              "Submitting..."
            ) : (
              <>
                <Send size={20} />
                Submit Missing Bench Report
              </>
            )}
          </SubmitButton>
        </FormSection>
      </Content>
    </PageContainer>
  )
}

export default ReportMissingBenchPage
