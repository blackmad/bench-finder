import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Heart, MessageCircle, Star, X } from "lucide-react"
import { useState } from "react"
import styled from "styled-components"
import { useAuth } from "../../contexts/AuthContext"
import { benchApi } from "../../services/api"

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[6]};
`

const Section = styled.div`
  background: ${({ theme }) => theme.colors.background};
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[6]};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const SectionTitle = styled.h3`
  font-size: ${({ theme }) => theme.typography.sizes.lg};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
`

const RatingContainer = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[4]};
`

const StarButton = styled.button<{ $active: boolean; $hoverable: boolean }>`
  background: none;
  border: none;
  padding: ${({ theme }) => theme.spacing[2]};
  cursor: ${({ $hoverable }) => ($hoverable ? "pointer" : "default")};
  color: ${({ $active, theme }) =>
    $active ? theme.colors.warning : theme.colors.gray400};
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ $hoverable, theme }) =>
      $hoverable ? theme.colors.warning : undefined};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const StatusButtons = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[2]};
  flex-wrap: wrap;
`

const StatusButton = styled.button<{ $active: boolean }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  border: 1px solid
    ${({ $active, theme }) =>
      $active ? theme.colors.primary : theme.colors.borderLight};
  background: ${({ $active, theme }) =>
    $active ? `${theme.colors.primary}20` : theme.colors.background};
  color: ${({ $active, theme }) =>
    $active ? theme.colors.primary : theme.colors.textSecondary};
  cursor: pointer;
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  transition: all ${({ theme }) => theme.transitions.fast};

  &:hover {
    border-color: ${({ theme }) => theme.colors.primary};
    background: ${({ theme }) => `${theme.colors.primary}10`};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const CommentsList = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[4]};
  margin-top: ${({ theme }) => theme.spacing[4]};
`

const CommentItem = styled.div`
  padding: ${({ theme }) => theme.spacing[4]};
  background: ${({ theme }) => theme.colors.backgroundSecondary};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
`

const CommentText = styled.p`
  margin: 0;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  line-height: 1.6;
`

const CommentMeta = styled.div`
  margin-top: ${({ theme }) => theme.spacing[2]};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  color: ${({ theme }) => theme.colors.textSecondary};
`

const CommentForm = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing[3]};
  margin-top: ${({ theme }) => theme.spacing[4]};
`

const CommentTextarea = styled.textarea`
  width: 100%;
  min-height: 100px;
  padding: ${({ theme }) => theme.spacing[3]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  background: ${({ theme }) => theme.colors.backgroundSecondary};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-family: inherit;
  resize: vertical;

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
  }
`

const SubmitButton = styled.button`
  align-self: flex-start;
  padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  border: none;
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  cursor: pointer;
  transition: background ${({ theme }) => theme.transitions.fast};

  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.primaryDark};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const LoginPrompt = styled.div`
  padding: ${({ theme }) => theme.spacing[4]};
  background: ${({ theme }) => theme.colors.backgroundSecondary};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  text-align: center;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
`

interface BenchUserInteractionsProps {
  benchId: number
}

export default function BenchUserInteractions({
  benchId,
}: BenchUserInteractionsProps) {
  const { user, loading: authLoading } = useAuth()
  const queryClient = useQueryClient()
  const [commentText, setCommentText] = useState("")

  // Fetch user data
  const { data: userDataResponse, isLoading } = useQuery({
    queryKey: ["benchUserData", benchId],
    queryFn: async () => {
      const response = await benchApi.getBenchUserData(benchId)
      return response.data
    },
    enabled: !!benchId,
  })

  const userData = userDataResponse

  // Rating mutation
  const rateMutation = useMutation({
    mutationFn: (rating: number) => benchApi.rateBench(benchId, rating),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchUserData", benchId] })
    },
  })

  // Delete rating mutation
  const deleteRatingMutation = useMutation({
    mutationFn: () => benchApi.deleteRating(benchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchUserData", benchId] })
    },
  })

  // Status mutation
  const statusMutation = useMutation({
    mutationFn: (status: string) => benchApi.setBenchStatus(benchId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchUserData", benchId] })
    },
  })

  // Remove status mutation
  const removeStatusMutation = useMutation({
    mutationFn: (status: string) => benchApi.removeBenchStatus(benchId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchUserData", benchId] })
    },
  })

  // Comment mutation
  const commentMutation = useMutation({
    mutationFn: (comment: string) => benchApi.addComment(benchId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchUserData", benchId] })
      setCommentText("")
    },
  })

  const handleRatingClick = (rating: number) => {
    if (!user) return
    if (userData?.user_rating?.rating === rating) {
      deleteRatingMutation.mutate()
    } else {
      rateMutation.mutate(rating)
    }
  }

  const handleStatusToggle = (status: string) => {
    if (!user) return
    const isActive = userData?.user_statuses?.some(
      (s: { status: string }) => s.status === status
    )
    if (isActive) {
      removeStatusMutation.mutate(status)
    } else {
      statusMutation.mutate(status)
    }
  }

  const handleCommentSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!user || !commentText.trim()) return
    commentMutation.mutate(commentText.trim())
  }

  if (authLoading || isLoading) {
    return <Container>Loading...</Container>
  }

  const userRating = userData?.user_rating?.rating || 0
  const activeStatuses =
    userData?.user_statuses?.map((s: { status: string }) => s.status) || []

  return (
    <Container>
      {/* Ratings */}
      <Section>
        <SectionTitle>
          <Star size={20} />
          Rating
          {userData?.average_rating && (
            <span style={{ marginLeft: "auto", fontSize: "0.875rem" }}>
              {userData.average_rating.toFixed(1)} ({userData.total_ratings})
            </span>
          )}
        </SectionTitle>
        {user ? (
          <RatingContainer>
            {[1, 2, 3, 4, 5].map((star) => (
              <StarButton
                key={star}
                $active={star <= userRating}
                $hoverable={!!user}
                onClick={() => handleRatingClick(star)}
                disabled={
                  rateMutation.isPending || deleteRatingMutation.isPending
                }
              >
                <Star
                  size={24}
                  fill={star <= userRating ? "currentColor" : "none"}
                />
              </StarButton>
            ))}
            {userRating > 0 && (
              <X
                size={16}
                style={{
                  cursor: "pointer",
                  color: "var(--color-text-secondary)",
                }}
                onClick={() => deleteRatingMutation.mutate()}
              />
            )}
          </RatingContainer>
        ) : (
          <LoginPrompt>Login to rate this bench</LoginPrompt>
        )}
      </Section>

      {/* Status Markers */}
      <Section>
        <SectionTitle>
          <Heart size={20} />
          Mark Bench
        </SectionTitle>
        {user ? (
          <StatusButtons>
            <StatusButton
              $active={activeStatuses.includes("been")}
              onClick={() => handleStatusToggle("been")}
              disabled={
                statusMutation.isPending || removeStatusMutation.isPending
              }
            >
              Been
            </StatusButton>
            <StatusButton
              $active={activeStatuses.includes("want_to_go")}
              onClick={() => handleStatusToggle("want_to_go")}
              disabled={
                statusMutation.isPending || removeStatusMutation.isPending
              }
            >
              Want to Go
            </StatusButton>
            <StatusButton
              $active={activeStatuses.includes("favorite")}
              onClick={() => handleStatusToggle("favorite")}
              disabled={
                statusMutation.isPending || removeStatusMutation.isPending
              }
            >
              <Heart
                size={16}
                fill={
                  activeStatuses.includes("favorite") ? "currentColor" : "none"
                }
              />
              Favorite
            </StatusButton>
          </StatusButtons>
        ) : (
          <LoginPrompt>Login to mark benches</LoginPrompt>
        )}
      </Section>

      {/* Comments */}
      <Section>
        <SectionTitle>
          <MessageCircle size={20} />
          Comments ({userData?.total_comments || 0})
        </SectionTitle>
        {user ? (
          <>
            <CommentForm onSubmit={handleCommentSubmit}>
              <CommentTextarea
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Add a comment about this bench..."
                maxLength={5000}
              />
              <SubmitButton
                type="submit"
                disabled={!commentText.trim() || commentMutation.isPending}
              >
                {commentMutation.isPending ? "Posting..." : "Post Comment"}
              </SubmitButton>
            </CommentForm>
            {userData?.user_comments && userData.user_comments.length > 0 && (
              <CommentsList>
                {userData.user_comments.map((comment: { id: number; comment: string; created_at: string }) => (
                  <CommentItem key={comment.id}>
                    <CommentText>{comment.comment}</CommentText>
                    <CommentMeta>
                      {new Date(comment.created_at).toLocaleDateString()}
                    </CommentMeta>
                  </CommentItem>
                ))}
              </CommentsList>
            )}
          </>
        ) : (
          <LoginPrompt>Login to view and add comments</LoginPrompt>
        )}
      </Section>
    </Container>
  )
}
