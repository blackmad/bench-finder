import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import CommentsService, { type CommentWithProfile } from '../services/commentsService'

export const useComments = (benchId: number) => {
  const { user } = useAuth()
  const [comments, setComments] = useState<CommentWithProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load comments for the bench
  const loadComments = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const commentsData = await CommentsService.getComments(benchId)
      setComments(commentsData)
    } catch (err) {
      setError('Failed to load comments')
      console.error('Error loading comments:', err)
    } finally {
      setLoading(false)
    }
  }, [benchId])

  // Load comments when benchId changes
  useEffect(() => {
    if (benchId) {
      loadComments()
    }
  }, [benchId, loadComments])

  const addComment = useCallback(async (content: string): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to comment')
    }

    if (!content.trim()) {
      throw new Error('Comment cannot be empty')
    }

    try {
      setError(null)
      const newComment = await CommentsService.addComment(user.id, benchId, content)
      setComments(prev => [...prev, newComment])
    } catch (err) {
      setError('Failed to add comment')
      console.error('Error adding comment:', err)
      throw err
    }
  }, [user, benchId])

  const updateComment = useCallback(async (commentId: string, content: string): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to update comments')
    }

    if (!content.trim()) {
      throw new Error('Comment cannot be empty')
    }

    try {
      setError(null)
      const updatedComment = await CommentsService.updateComment(commentId, content)
      setComments(prev => 
        prev.map(comment => 
          comment.id === commentId ? updatedComment : comment
        )
      )
    } catch (err) {
      setError('Failed to update comment')
      console.error('Error updating comment:', err)
      throw err
    }
  }, [user])

  const deleteComment = useCallback(async (commentId: string): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to delete comments')
    }

    try {
      setError(null)
      await CommentsService.deleteComment(commentId)
      setComments(prev => prev.filter(comment => comment.id !== commentId))
    } catch (err) {
      setError('Failed to delete comment')
      console.error('Error deleting comment:', err)
      throw err
    }
  }, [user])

  const canEditComment = useCallback((comment: CommentWithProfile): boolean => {
    return !!user && comment.user_id === user.id
  }, [user])

  return {
    comments,
    loading,
    error,
    addComment,
    updateComment,
    deleteComment,
    canEditComment,
    refreshComments: loadComments,
    isLoggedIn: !!user
  }
}

export default useComments