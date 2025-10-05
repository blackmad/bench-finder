import { AnimatePresence, motion } from "framer-motion"
import { X } from "lucide-react"
import type React from "react"
import { useEffect } from "react"
import styled from "styled-components"
import type { Bench } from "../../types"

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
  bench: Bench | null
  imageUrl: string | null
  imageId: number | null
}

const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  bench,
  imageUrl,
  imageId,
}) => {
  // Close modal on escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener("keydown", handleEscape)
      document.body.style.overflow = "hidden"
    }

    return () => {
      document.removeEventListener("keydown", handleEscape)
      document.body.style.overflow = "unset"
    }
  }, [isOpen, onClose])

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
              <ModalTitle>Bench #{bench.id} - Detection Details</ModalTitle>
              <CloseButton onClick={onClose}>
                <X />
              </CloseButton>
            </ModalHeader>

            <ModalContent>
              {imageUrl ? (
                <ImageContainer>
                  <ModalImage src={imageUrl} alt={`Bench ${bench.id}`} />
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

              {/* TODO: Add segmentation visualization here if imageId is available */}
              {imageId && (
                <PlaceholderContent>
                  <p>Segmentation data visualization would appear here</p>
                  <small>Image ID: {imageId}</small>
                </PlaceholderContent>
              )}
            </ModalContent>
          </ModalContainer>
        </Overlay>
      )}
    </AnimatePresence>
  )
}

export default Modal
