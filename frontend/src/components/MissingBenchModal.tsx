import React, { useState, useEffect, useRef } from 'react'
import styled from 'styled-components'
import { X, MapPin, Send, Upload } from 'lucide-react'
import L from 'leaflet'
import { useAuth } from '../contexts/AuthContext'
import MissingBenchService from '../services/missingBenchService'
import 'leaflet/dist/leaflet.css'

interface MissingBenchModalProps {
  isOpen: boolean
  onClose: () => void
  initialLat?: number
  initialLng?: number
}

const Overlay = styled.div`
  position: fixed
  top: 0
  left: 0
  right: 0
  bottom: 0
  background: rgba(0, 0, 0, 0.5)
  display: flex
  justify-content: center
  align-items: center
  z-index: 1000
  padding: 1rem
`

const Modal = styled.div`
  background: white
  border-radius: 12px
  width: 100%
  max-width: 600px
  max-height: 90vh
  overflow: hidden
  position: relative
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)
`

const Header = styled.div`
  padding: 1.5rem
  border-bottom: 1px solid ${props => props.theme.colors.borderLight}
  display: flex
  justify-content: space-between
  align-items: center
`

const Title = styled.h2`
  margin: 0
  color: ${props => props.theme.colors.textPrimary}
  font-size: 1.25rem
  font-weight: 600
  display: flex
  align-items: center
  gap: 0.5rem
  
  .icon {
    width: 24px
    height: 24px
    color: ${props => props.theme.colors.primary}
  }
`

const CloseButton = styled.button`
  background: none
  border: none
  cursor: pointer
  color: ${props => props.theme.colors.textSecondary}
  padding: 0.5rem
  border-radius: 6px
  transition: all 0.2s
  
  &:hover {
    color: ${props => props.theme.colors.textPrimary}
    background: ${props => props.theme.colors.backgroundSecondary}
  }
  
  .icon {
    width: 20px
    height: 20px
  }
`

const Content = styled.div`
  padding: 1.5rem
  max-height: calc(90vh - 120px)
  overflow-y: auto
`

const Instructions = styled.div`
  background: ${props => props.theme.colors.backgroundSecondary}
  padding: 1rem
  border-radius: 8px
  margin-bottom: 1.5rem
  font-size: 0.9rem
  color: ${props => props.theme.colors.textSecondary}
`

const MapContainer = styled.div`
  height: 300px
  border-radius: 8px
  overflow: hidden
  margin-bottom: 1.5rem
  border: 2px solid ${props => props.theme.colors.border}
  position: relative
  
  .leaflet-container {
    height: 100%
    width: 100%
  }
`

const CoordinateDisplay = styled.div`
  background: ${props => props.theme.colors.backgroundSecondary}
  padding: 0.75rem
  border-radius: 6px
  margin-bottom: 1rem
  font-family: ${props => props.theme.typography.fonts.mono}
  font-size: 0.9rem
  color: ${props => props.theme.colors.textSecondary}
  display: flex
  align-items: center
  gap: 0.5rem
  
  .icon {
    width: 16px
    height: 16px
    color: ${props => props.theme.colors.primary}
  }
`

const Form = styled.form`
  display: flex
  flex-direction: column
  gap: 1rem
`

const InputGroup = styled.div`
  display: flex
  flex-direction: column
  gap: 0.5rem
`

const Label = styled.label`
  font-weight: 500
  color: ${props => props.theme.colors.textPrimary}
  font-size: 0.9rem
`

const TextArea = styled.textarea`
  width: 100%
  min-height: 80px
  padding: 0.75rem
  border: 2px solid ${props => props.theme.colors.border}
  border-radius: 6px
  font-size: 0.9rem
  font-family: inherit
  resize: vertical
  transition: border-color 0.2s
  
  &:focus {
    outline: none
    border-color: ${props => props.theme.colors.primary}
  }
  
  &::placeholder {
    color: ${props => props.theme.colors.textTertiary}
  }
`

const FileInput = styled.input`
  display: none
`

const FileInputLabel = styled.label`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.75rem
  border: 2px dashed ${props => props.theme.colors.border}
  border-radius: 6px
  cursor: pointer
  transition: all 0.2s
  color: ${props => props.theme.colors.textSecondary}
  font-size: 0.9rem
  
  &:hover {
    border-color: ${props => props.theme.colors.primary}
    color: ${props => props.theme.colors.primary}
  }
  
  .icon {
    width: 16px
    height: 16px
  }
`

const Actions = styled.div`
  display: flex
  gap: 0.75rem
  justify-content: flex-end
  margin-top: 1.5rem
`

const Button = styled.button<{ $variant?: 'primary' | 'secondary' }>`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.75rem 1.5rem
  border-radius: 6px
  font-weight: 500
  cursor: pointer
  transition: all 0.2s
  font-size: 0.9rem
  
  ${props => props.$variant === 'primary' ? `
    background: ${props.theme.colors.primary};
    color: white;
    border: 2px solid ${props.theme.colors.primary};
    
    &:hover {
      background: ${props.theme.colors.primaryHover};
      border-color: ${props.theme.colors.primaryHover};
    }
  ` : `
    background: white;
    color: ${props.theme.colors.textPrimary};
    border: 2px solid ${props.theme.colors.border};
    
    &:hover {
      border-color: ${props.theme.colors.primary};
    }
  `}
  
  &:disabled {
    opacity: 0.6
    cursor: not-allowed
  }
  
  .icon {
    width: 16px
    height: 16px
  }
`

const ErrorMessage = styled.div`
  background: #fee2e2
  color: #dc2626
  padding: 0.75rem
  border-radius: 6px
  font-size: 0.9rem
  margin-bottom: 1rem
`

const SuccessMessage = styled.div`
  background: #dcfce7
  color: #166534
  padding: 0.75rem
  border-radius: 6px
  font-size: 0.9rem
  margin-bottom: 1rem
`

export const MissingBenchModal: React.FC<MissingBenchModalProps> = ({
  isOpen,
  onClose,
  initialLat = 52.3613577,
  initialLng = 4.8666322
}) => {
  const { user } = useAuth()
  const [map, setMap] = useState<L.Map | null>(null)
  const [marker, setMarker] = useState<L.Marker | null>(null)
  const [selectedLocation, setSelectedLocation] = useState<{ lat: number; lng: number } | null>(null)
  const [description, setDescription] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  
  const mapRef = useRef<HTMLDivElement>(null)

  // Initialize map
  useEffect(() => {
    if (!isOpen || !mapRef.current || map) return

    const newMap = L.map(mapRef.current).setView([initialLat, initialLng], 15)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(newMap)

    // Custom marker icon
    const markerIcon = L.divIcon({
      html: '📍',
      className: 'custom-marker',
      iconSize: [30, 30],
      iconAnchor: [15, 30],
    })

    // Add click handler
    newMap.on('click', (e: L.LeafletMouseEvent) => {
      setSelectedLocation({ lat: e.latlng.lat, lng: e.latlng.lng })
      
      // Remove existing marker
      if (marker) {
        newMap.removeLayer(marker)
      }
      
      // Add new marker
      const newMarker = L.marker([e.latlng.lat, e.latlng.lng], { icon: markerIcon })
        .addTo(newMap)
      
      setMarker(newMarker)
    })

    setMap(newMap)

    // Cleanup
    return () => {
      newMap.remove()
      setMap(null)
      setMarker(null)
    }
  }, [isOpen, initialLat, initialLng, map, marker])

  // Reset form when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedLocation(null)
      setDescription('')
      setImage(null)
      setError(null)
      setSuccess(false)
      if (marker && map) {
        map.removeLayer(marker)
        setMarker(null)
      }
    }
  }, [isOpen, marker, map])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!user) {
      setError('You must be logged in to report missing benches')
      return
    }

    if (!selectedLocation) {
      setError('Please select a location on the map')
      return
    }

    if (!description.trim()) {
      setError('Please provide a description')
      return
    }

    try {
      setIsSubmitting(true)
      setError(null)

      // TODO: Handle image upload if needed
      let imageUrl: string | undefined

      await MissingBenchService.reportMissingBench(
        user.id,
        selectedLocation.lat,
        selectedLocation.lng,
        description,
        imageUrl
      )

      setSuccess(true)
      setTimeout(() => {
        onClose()
      }, 2000)

    } catch (err) {
      setError('Failed to submit report. Please try again.')
      console.error('Error submitting missing bench report:', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        setError('Please select a valid image file')
        return
      }
      
      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setError('Image must be smaller than 5MB')
        return
      }
      
      setImage(file)
      setError(null)
    }
  }

  if (!isOpen) return null

  return (
    <Overlay onClick={onClose}>
      <Modal onClick={(e) => e.stopPropagation()}>
        <Header>
          <Title>
            <MapPin className="icon" />
            Report Missing Bench
          </Title>
          <CloseButton onClick={onClose}>
            <X className="icon" />
          </CloseButton>
        </Header>

        <Content>
          <Instructions>
            Click on the map to select the location where you believe there should be a bench. 
            Provide a description to help us understand why this location would benefit from a bench.
          </Instructions>

          <MapContainer>
            <div ref={mapRef} />
          </MapContainer>

          {selectedLocation && (
            <CoordinateDisplay>
              <MapPin className="icon" />
              Selected: {selectedLocation.lat.toFixed(6)}, {selectedLocation.lng.toFixed(6)}
            </CoordinateDisplay>
          )}

          {error && <ErrorMessage>{error}</ErrorMessage>}
          {success && <SuccessMessage>Report submitted successfully!</SuccessMessage>}

          <Form onSubmit={handleSubmit}>
            <InputGroup>
              <Label htmlFor="description">Description *</Label>
              <TextArea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe why this location would benefit from a bench (e.g., busy walking area, near bus stop, scenic viewpoint)..."
                required
                maxLength={500}
              />
            </InputGroup>

            <InputGroup>
              <Label>Photo (optional)</Label>
              <FileInputLabel htmlFor="image-upload">
                <Upload className="icon" />
                {image ? `Selected: ${image.name}` : 'Choose an image of the location'}
              </FileInputLabel>
              <FileInput
                id="image-upload"
                type="file"
                accept="image/*"
                onChange={handleFileChange}
              />
            </InputGroup>

            <Actions>
              <Button type="button" onClick={onClose} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button 
                type="submit" 
                $variant="primary" 
                disabled={!selectedLocation || !description.trim() || isSubmitting}
              >
                <Send className="icon" />
                {isSubmitting ? 'Submitting...' : 'Submit Report'}
              </Button>
            </Actions>
          </Form>
        </Content>
      </Modal>
    </Overlay>
  )
}

export default MissingBenchModal