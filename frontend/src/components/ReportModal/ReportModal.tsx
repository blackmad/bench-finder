import { AnimatePresence, motion } from "framer-motion"
import { AlertTriangle, Check, MapPin, Send, X } from "lucide-react"
import { useEffect, useId, useState } from "react"
import styled from "styled-components"
import type { WebBenchData } from "../../api"
import { BenchReportType } from "../../api"
import { benchApi } from "../../services/api"
import { getCurrentLocation } from "../../utils/imageCapture"

const Overlay = styled(motion.div)`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1080;
  padding: ${({ theme }) => theme.spacing[4]};
`

const Modal = styled(motion.div)`
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  box-shadow: ${({ theme }) => theme.shadows.xl};
`

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: ${({ theme }) => theme.spacing[6]};
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const Title = styled.h2`
  font-size: ${({ theme }) => theme.typography.sizes.xl};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  color: ${({ theme }) => theme.colors.textPrimary};
  margin: 0;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};

  svg {
    color: ${({ theme }) => theme.colors.warning};
  }
`

const CloseButton = styled.button`
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

const Content = styled.div`
  padding: ${({ theme }) => theme.spacing[6]};
`

const BenchInfo = styled.div`
  background: ${({ theme }) => theme.colors.gray50};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[4]};
  margin-bottom: ${({ theme }) => theme.spacing[6]};
`

const BenchInfoItem = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  margin-bottom: ${({ theme }) => theme.spacing[2]};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  color: ${({ theme }) => theme.colors.textSecondary};

  &:last-child {
    margin-bottom: 0;
  }

  svg {
    width: 16px;
    height: 16px;
    color: ${({ theme }) => theme.colors.textTertiary};
  }
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

const Select = styled.select`
  width: 100%;
  padding: ${({ theme }) => theme.spacing[3]};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  color: ${({ theme }) => theme.colors.textPrimary};
  background: ${({ theme }) => theme.colors.background};
  transition: border-color ${({ theme }) => theme.transitions.fast};

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
  }
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

const ImagePreview = styled.div`
  border: 2px dashed ${({ theme }) => theme.colors.borderLight};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[4]};
  text-align: center;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-bottom: ${({ theme }) => theme.spacing[4]};

  img {
    max-width: 100%;
    max-height: 200px;
    border-radius: ${({ theme }) => theme.borderRadius.md};
    margin-bottom: ${({ theme }) => theme.spacing[2]};
  }
`

const Footer = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[3]};
  padding: ${({ theme }) => theme.spacing[6]};
  border-top: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const Button = styled.button<{ $variant?: "primary" | "secondary" }>`
  flex: 1;
  padding: ${({ theme }) => theme.spacing[3]} ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  cursor: pointer;
  transition: all ${({ theme }) => theme.transitions.fast};
  display: flex;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing[2]};

  ${({ $variant = "secondary", theme }) =>
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

const SuccessMessage = styled(motion.div)`
  text-align: center;
  padding: ${({ theme }) => theme.spacing[8]} ${({ theme }) => theme.spacing[6]};
  color: ${({ theme }) => theme.colors.success};

  svg {
    width: 48px;
    height: 48px;
    margin-bottom: ${({ theme }) => theme.spacing[4]};
  }

  h3 {
    font-size: ${({ theme }) => theme.typography.sizes.lg};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
  }

  p {
    margin: 0;
    color: ${({ theme }) => theme.colors.textSecondary};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
  }
`

interface ReportModalProps {
  bench: WebBenchData
  imageUrl?: string
  imageId?: number
  isOpen: boolean
  onClose: () => void
}

const getReportTypes = (benchFound: boolean | undefined) => [
  {
    value: BenchReportType.BAD_DETECTION,
    label:
      benchFound === false
        ? "Bench visible in photo but not detected"
        : "Bad Detection - No bench here",
  },
  { value: BenchReportType.INCORRECT_LOCATION, label: "Incorrect Location" },
  { value: BenchReportType.POOR_IMAGE_QUALITY, label: "Poor Image Quality" },
]

export const ReportModal: React.FC<ReportModalProps> = ({
  bench,
  imageUrl,
  imageId,
  isOpen,
  onClose,
}) => {
  const [reportType, setReportType] = useState(BenchReportType.BAD_DETECTION)
  const [description, setDescription] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [userLocation, setUserLocation] = useState<{
    lat: number
    lng: number
  } | null>(null)

  const reportTypeId = useId()
  const descriptionId = useId()

  // Update report types based on whether bench was detected
  const reportTypes = getReportTypes(bench.bench_found)

  // Reset form when modal opens/closes or bench changes
  useEffect(() => {
    if (isOpen) {
      setReportType(BenchReportType.BAD_DETECTION)
      setDescription("")
      setIsSuccess(false)
      setUserLocation(null)
    }
  }, [isOpen])

  const handleSubmit = async () => {
    if (isSubmitting) return

    setIsSubmitting(true)

    try {
      // Try to get user's location
      let location = userLocation
      if (!location) {
        try {
          const pos = await getCurrentLocation()
          location = { lat: pos.lat, lng: pos.lng }
          setUserLocation(location)
        } catch {
          // Continue without location
        }
      }

      await benchApi.reportBadBench({
        benchId: bench.id,
        reportType: reportType,
        description: description || undefined,
        imageId: imageId || undefined,
        userLocationLat: location?.lat,
        userLocationLng: location?.lng,
      })

      setIsSuccess(true)

      // Auto-close after 3 seconds
      setTimeout(() => {
        onClose()
        setIsSuccess(false)
        setReportType(BenchReportType.BAD_DETECTION)
        setDescription("")
        setUserLocation(null)
      }, 3000)
    } catch (error) {
      console.error("Failed to submit report:", error)
      alert("Failed to submit report. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <Overlay
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose()
        }}
      >
        <Modal
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 500 }}
        >
          {isSuccess ? (
            <SuccessMessage
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
            >
              <Check />
              <h3>Report Submitted</h3>
              <p>Thank you for your feedback. We'll review this report soon.</p>
            </SuccessMessage>
          ) : (
            <>
              <Header>
                <Title>
                  <AlertTriangle size={20} />
                  Report Issue
                </Title>
                <CloseButton onClick={onClose}>
                  <X size={20} />
                </CloseButton>
              </Header>

              <Content>
                <BenchInfo>
                  <BenchInfoItem>
                    <MapPin size={16} />
                    Bench #{bench.id} at {bench.lat.toFixed(6)},{" "}
                    {bench.lng.toFixed(6)}
                  </BenchInfoItem>
                  <BenchInfoItem>
                    Source: {bench.source} • Confidence:{" "}
                    {(bench.best_confidence * 100).toFixed(0)}%
                  </BenchInfoItem>
                </BenchInfo>

                <FormGroup>
                  <Label htmlFor={reportTypeId}>What's the issue?</Label>
                  <Select
                    id={reportTypeId}
                    value={reportType}
                    onChange={(e) =>
                      setReportType(e.target.value as BenchReportType)
                    }
                  >
                    {reportTypes.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </Select>
                </FormGroup>

                <FormGroup>
                  <Label htmlFor={descriptionId}>Additional Details</Label>
                  <Textarea
                    id={descriptionId}
                    placeholder="Please describe the issue in more detail..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </FormGroup>

                {imageUrl && (
                  <FormGroup>
                    <Label>Reported Image</Label>
                    <ImagePreview>
                      <img src={imageUrl} alt="Bench detection" />
                      <div>This image will be included with your report</div>
                    </ImagePreview>
                  </FormGroup>
                )}
              </Content>

              <Footer>
                <Button onClick={onClose} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button
                  $variant="primary"
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    "Submitting..."
                  ) : (
                    <>
                      <Send size={16} />
                      Submit Report
                    </>
                  )}
                </Button>
              </Footer>
            </>
          )}
        </Modal>
      </Overlay>
    </AnimatePresence>
  )
}

export default ReportModal
