import React, { useState } from 'react'
import styled from 'styled-components'
import { MessageSquare, Send, Edit, Trash2, X, Check } from 'lucide-react'
import { useComments } from '../../hooks/useComments'
import { useAuth } from '../../contexts/AuthContext'
import type { CommentWithProfile } from '../../services/commentsService'

interface CommentsSectionProps {
  benchId: number
  className?: string
}

const Container = styled.div`
  display: flex
  flex-direction: column
  gap: 1rem
`

const Header = styled.div`
  display: flex
  align-items: center
  gap: 0.5rem
  margin-bottom: 1rem
  
  .icon {
    width: 20px
    height: 20px
    color: ${props => props.theme.colors.textSecondary}
  }
  
  h3 {
    margin: 0
    font-size: 1.125rem
    font-weight: 600
    color: ${props => props.theme.colors.textPrimary}
  }
  
  .count {
    background: ${props => props.theme.colors.gray200}
    color: ${props => props.theme.colors.textSecondary}
    padding: 0.25rem 0.5rem
    border-radius: 12px
    font-size: 0.8rem
    font-weight: 500
  }
`

const CommentForm = styled.form`
  display: flex
  flex-direction: column
  gap: 0.75rem
  padding: 1rem
  background: ${props => props.theme.colors.backgroundSecondary}
  border-radius: 8px
  border: 2px solid ${props => props.theme.colors.border}
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

const FormActions = styled.div`
  display: flex
  justify-content: space-between
  align-items: center
  gap: 0.5rem
`

const CharCount = styled.span<{ $isNearLimit: boolean }>`
  font-size: 0.8rem
  color: ${props => props.$isNearLimit 
    ? props.theme.colors.warning 
    : props.theme.colors.textTertiary
  }
`

const Button = styled.button<{ 
  $variant?: 'primary' | 'secondary' | 'danger'
  $size?: 'small' | 'medium'
}>`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: ${props => props.$size === 'small' ? '0.375rem 0.75rem' : '0.5rem 1rem'}
  border-radius: 6px
  font-weight: 500
  cursor: pointer
  transition: all 0.2s
  font-size: ${props => props.$size === 'small' ? '0.8rem' : '0.9rem'}
  
  ${props => {
    switch (props.$variant) {
      case 'primary':
        return `
          background: ${props.theme.colors.primary};
          color: white;
          border: 2px solid ${props.theme.colors.primary};
          
          &:hover {
            background: ${props.theme.colors.primaryHover};
            border-color: ${props.theme.colors.primaryHover};
          }
        `
      case 'danger':
        return `
          background: ${props.theme.colors.error};
          color: white;
          border: 2px solid ${props.theme.colors.error};
          
          &:hover {
            background: ${props.theme.colors.errorLight};
            border-color: ${props.theme.colors.errorLight};
          }
        `
      default:
        return `
          background: white;
          color: ${props.theme.colors.textPrimary};
          border: 2px solid ${props.theme.colors.border};
          
          &:hover {
            border-color: ${props.theme.colors.primary};
          }
        `
    }
  }}
  
  &:disabled {
    opacity: 0.6
    cursor: not-allowed
  }
  
  .icon {
    width: 16px
    height: 16px
  }
`

const CommentsList = styled.div`
  display: flex
  flex-direction: column
  gap: 1rem
`

const Comment = styled.div`
  background: white
  border: 1px solid ${props => props.theme.colors.borderLight}
  border-radius: 8px
  padding: 1rem
`

const CommentHeader = styled.div`
  display: flex
  justify-content: space-between
  align-items: flex-start
  margin-bottom: 0.75rem
`

const UserInfo = styled.div`
  display: flex
  align-items: center
  gap: 0.75rem
`

const Avatar = styled.div`
  width: 32px
  height: 32px
  border-radius: 50%
  background: ${props => props.theme.colors.primary}
  color: white
  display: flex
  align-items: center
  justify-content: center
  font-weight: 500
  font-size: 0.9rem
`

const UserDetails = styled.div`
  display: flex
  flex-direction: column
  
  .name {
    font-weight: 500
    color: ${props => props.theme.colors.textPrimary}
    font-size: 0.9rem
  }
  
  .date {
    font-size: 0.8rem
    color: ${props => props.theme.colors.textSecondary}
  }
`

const CommentActions = styled.div`
  display: flex
  gap: 0.5rem
`

const CommentContent = styled.div`
  color: ${props => props.theme.colors.textPrimary}
  line-height: 1.5
  font-size: 0.95rem
  white-space: pre-wrap
`

const EditForm = styled.form`
  display: flex
  flex-direction: column
  gap: 0.5rem
  margin-top: 0.75rem
`

const LoginPrompt = styled.div`
  text-align: center
  padding: 2rem 1rem
  color: ${props => props.theme.colors.textSecondary}
  background: ${props => props.theme.colors.backgroundSecondary}
  border-radius: 8px
  border: 2px dashed ${props => props.theme.colors.border}
  
  .message {
    margin-bottom: 1rem
  }
`

const LoadingSpinner = styled.div`
  display: flex
  justify-content: center
  padding: 2rem
  color: ${props => props.theme.colors.textSecondary}
`

const MAX_COMMENT_LENGTH = 500

export const CommentsSection: React.FC<CommentsSectionProps> = ({
  benchId,
  className
}) => {
  const { user } = useAuth()
  const {
    comments,
    loading,
    error,
    addComment,
    updateComment,
    deleteComment,
    canEditComment,
    isLoggedIn
  } = useComments(benchId)

  const [newComment, setNewComment] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingContent, setEditingContent] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newComment.trim() || isSubmitting) return

    try {
      setIsSubmitting(true)
      await addComment(newComment)
      setNewComment('')
    } catch (error) {
      console.error('Failed to add comment:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleEdit = (comment: CommentWithProfile) => {
    setEditingId(comment.id)
    setEditingContent(comment.content)
  }

  const handleUpdateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingId || !editingContent.trim()) return

    try {
      await updateComment(editingId, editingContent)
      setEditingId(null)
      setEditingContent('')
    } catch (error) {
      console.error('Failed to update comment:', error)
    }
  }

  const handleDelete = async (commentId: string) => {
    if (!confirm('Are you sure you want to delete this comment?')) return

    try {
      await deleteComment(commentId)
    } catch (error) {
      console.error('Failed to delete comment:', error)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)

    if (diffInHours < 24) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } else if (diffInHours < 24 * 7) {
      return date.toLocaleDateString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }
  }

  const getInitials = (name: string | null | undefined, email?: string) => {
    if (name) {
      return name
        .split(' ')
        .map(part => part.charAt(0))
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }
    return email?.charAt(0).toUpperCase() || 'U'
  }

  if (loading) {
    return (
      <Container className={className}>
        <LoadingSpinner>Loading comments...</LoadingSpinner>
      </Container>
    )
  }

  return (
    <Container className={className}>
      <Header>
        <MessageSquare className="icon" />
        <h3>Comments</h3>
        {comments.length > 0 && (
          <span className="count">{comments.length}</span>
        )}
      </Header>

      {isLoggedIn ? (
        <CommentForm onSubmit={handleSubmit}>
          <TextArea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value.slice(0, MAX_COMMENT_LENGTH))}
            placeholder="Share your thoughts about this bench..."
            disabled={isSubmitting}
          />
          <FormActions>
            <CharCount $isNearLimit={newComment.length > MAX_COMMENT_LENGTH * 0.8}>
              {newComment.length}/{MAX_COMMENT_LENGTH}
            </CharCount>
            <Button
              type="submit"
              $variant="primary"
              disabled={!newComment.trim() || isSubmitting}
            >
              <Send className="icon" />
              {isSubmitting ? 'Posting...' : 'Post Comment'}
            </Button>
          </FormActions>
        </CommentForm>
      ) : (
        <LoginPrompt>
          <div className="message">Sign in to share your thoughts about this bench</div>
        </LoginPrompt>
      )}

      {error && (
        <div style={{ color: 'red', fontSize: '0.9rem', padding: '0.5rem' }}>
          {error}
        </div>
      )}

      <CommentsList>
        {comments.map((comment) => (
          <Comment key={comment.id}>
            <CommentHeader>
              <UserInfo>
                <Avatar>
                  {comment.profiles?.avatar_url ? (
                    <img 
                      src={comment.profiles.avatar_url} 
                      alt="Avatar" 
                      style={{ width: '100%', height: '100%', borderRadius: '50%' }}
                    />
                  ) : (
                    getInitials(
                      comment.profiles?.full_name || comment.profiles?.username
                    )
                  )}
                </Avatar>
                <UserDetails>
                  <div className="name">
                    {comment.profiles?.full_name || 
                     comment.profiles?.username || 
                     'Anonymous User'}
                  </div>
                  <div className="date">
                    {formatDate(comment.created_at)}
                  </div>
                </UserDetails>
              </UserInfo>
              
              {canEditComment(comment) && (
                <CommentActions>
                  <Button
                    $size="small"
                    onClick={() => handleEdit(comment)}
                    disabled={editingId === comment.id}
                  >
                    <Edit className="icon" />
                  </Button>
                  <Button
                    $size="small"
                    $variant="danger"
                    onClick={() => handleDelete(comment.id)}
                  >
                    <Trash2 className="icon" />
                  </Button>
                </CommentActions>
              )}
            </CommentHeader>

            {editingId === comment.id ? (
              <EditForm onSubmit={handleUpdateSubmit}>
                <TextArea
                  value={editingContent}
                  onChange={(e) => setEditingContent(e.target.value.slice(0, MAX_COMMENT_LENGTH))}
                  autoFocus
                />
                <FormActions>
                  <CharCount $isNearLimit={editingContent.length > MAX_COMMENT_LENGTH * 0.8}>
                    {editingContent.length}/{MAX_COMMENT_LENGTH}
                  </CharCount>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <Button
                      type="button"
                      $size="small"
                      onClick={() => {
                        setEditingId(null)
                        setEditingContent('')
                      }}
                    >
                      <X className="icon" />
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      $size="small"
                      $variant="primary"
                      disabled={!editingContent.trim()}
                    >
                      <Check className="icon" />
                      Save
                    </Button>
                  </div>
                </FormActions>
              </EditForm>
            ) : (
              <CommentContent>{comment.content}</CommentContent>
            )}
          </Comment>
        ))}
        
        {comments.length === 0 && !loading && (
          <div style={{ 
            textAlign: 'center', 
            padding: '2rem', 
            color: '#64748b' 
          }}>
            No comments yet. Be the first to share your thoughts!
          </div>
        )}
      </CommentsList>
    </Container>
  )
}

export default CommentsSection