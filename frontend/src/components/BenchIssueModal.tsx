import React, { useState } from 'react'
import styled from 'styled-components'
import { X, AlertTriangle, Send, Upload } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import BenchIssueService, { type IssueType } from '../services/benchIssueService'

interface BenchIssueModalProps {
  isOpen: boolean
  onClose: () => void
  benchId: number
  benchTitle?: string
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
  max-width: 500px
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
    color: ${props => props.theme.colors.warning}
  }
`

const BenchInfo = styled.div`
  font-size: 0.9rem
  color: ${props => props.theme.colors.textSecondary}
  margin-top: 0.25rem
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

const Form = styled.form`
  display: flex
  flex-direction: column
  gap: 1.5rem
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

const IssueTypeGrid = styled.div`
  display: grid
  grid-template-columns: repeat(2, 1fr)
  gap: 0.75rem
`

const IssueTypeButton = styled.button<{ $selected: boolean }>`
  padding: 1rem
  border-radius: 8px
  font-weight: 500
  cursor: pointer
  transition: all 0.2s
  text-align: left
  display: flex
  flex-direction: column
  gap: 0.25rem
  
  ${props => props.$selected ? `
    background: ${props.theme.colors.primary};
    color: white;
    border: 2px solid ${props.theme.colors.primary};
  ` : `
    background: white;
    color: ${props.theme.colors.textPrimary};
    border: 2px solid ${props.theme.colors.border};
    
    &:hover {
      border-color: ${props.theme.colors.primary};
      background: ${props.theme.colors.backgroundSecondary};
    }
  `}
  
  .title {
    font-size: 0.9rem
    font-weight: 600
  }
  
  .description {
    font-size: 0.8rem
    opacity: 0.8
  }
`

const TextArea = styled.textarea`
  width: 100%
  min-height: 100px
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
    background: ${props.theme.colors.warning};
    color: white;
    border: 2px solid ${props.theme.colors.warning};
    
    &:hover {
      background: ${props.theme.colors.warningLight};
      border-color: ${props.theme.colors.warningLight};
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

const ISSUE_TYPES: Array<{
  value: IssueType
  title: string
  description: string
}> = [
  {
    value: 'damaged',
    title: 'Damaged',
    description: 'Bench is broken or needs repair'
  },
  {
    value: 'missing',
    title: 'Missing',
    description: 'Bench has been removed or stolen'
  },
  {
    value: 'inappropriate',
    title: 'Inappropriate',
    description: 'Content or location is inappropriate'
  },
  {
    value: 'other',
    title: 'Other',
    description: 'Other issues or concerns'
  }
]

export const BenchIssueModal: React.FC<BenchIssueModalProps> = ({
  isOpen,
  onClose,
  benchId,
  benchTitle
}) => {
  const { user } = useAuth()
  const [selectedIssueType, setSelectedIssueType] = useState<IssueType | null>(null)
  const [description, setDescription] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  // Reset form when modal opens/closes
  React.useEffect(() => {
    if (!isOpen) {
      setSelectedIssueType(null)
      setDescription('')
      setImage(null)
      setError(null)
      setSuccess(false)
    }
  }, [isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!user) {
      setError('You must be logged in to report issues')
      return
    }

    if (!selectedIssueType) {
      setError('Please select an issue type')
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

      await BenchIssueService.reportIssue(
        user.id,
        benchId,
        selectedIssueType,
        description,
        imageUrl
      )

      setSuccess(true)
      setTimeout(() => {
        onClose()
      }, 2000)

    } catch (err) {
      setError('Failed to submit report. Please try again.')
      console.error('Error submitting bench issue report:', err)
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
          <div>
            <Title>
              <AlertTriangle className="icon" />
              Report Issue
            </Title>
            {benchTitle && (
              <BenchInfo>Report an issue with {benchTitle}</BenchInfo>
            )}
          </div>
          <CloseButton onClick={onClose}>
            <X className="icon" />
          </CloseButton>
        </Header>

        <Content>
          {error && <ErrorMessage>{error}</ErrorMessage>}
          {success && <SuccessMessage>Issue report submitted successfully!</SuccessMessage>}

          <Form onSubmit={handleSubmit}>
            <InputGroup>
              <Label>Issue Type *</Label>
              <IssueTypeGrid>
                {ISSUE_TYPES.map((issueType) => (
                  <IssueTypeButton
                    key={issueType.value}
                    type="button"
                    $selected={selectedIssueType === issueType.value}
                    onClick={() => setSelectedIssueType(issueType.value)}
                  >
                    <div className="title">{issueType.title}</div>
                    <div className="description">{issueType.description}</div>
                  </IssueTypeButton>
                ))}
              </IssueTypeGrid>
            </InputGroup>

            <InputGroup>
              <Label htmlFor="description">Description *</Label>
              <TextArea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Please provide details about the issue you're reporting..."
                required
                maxLength={1000}
              />
            </InputGroup>

            <InputGroup>
              <Label>Photo (optional)</Label>
              <FileInputLabel htmlFor="image-upload">
                <Upload className="icon" />
                {image ? `Selected: ${image.name}` : 'Choose an image to help illustrate the issue'}
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
                disabled={!selectedIssueType || !description.trim() || isSubmitting}
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

export default BenchIssueModal