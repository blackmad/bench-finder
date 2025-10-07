import React, { useState, useEffect } from 'react'
import styled from 'styled-components'
import { User, Heart, MessageSquare, MapPin, AlertTriangle, Settings, Edit, Save, X } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import Navigation from '../components/Navigation'
import FavoritesService from '../services/favoritesService'
import CommentsService, { type CommentWithProfile } from '../services/commentsService'
import MissingBenchService from '../services/missingBenchService'
import BenchIssueService from '../services/benchIssueService'
import type { Database } from '../types/database'

type BenchFavorite = Database['public']['Tables']['bench_favorites']['Row']
type MissingBenchReport = Database['public']['Tables']['missing_bench_reports']['Row']
type BenchIssueReport = Database['public']['Tables']['bench_issue_reports']['Row']

const PageContainer = styled.div`
  min-height: 100vh
  background: ${props => props.theme.colors.backgroundSecondary}
`

const Container = styled.div`
  max-width: 1200px
  margin: 0 auto
  padding: 2rem 1rem
`

const Header = styled.div`
  background: white
  border-radius: 12px
  padding: 2rem
  margin-bottom: 2rem
  display: flex
  gap: 2rem
  align-items: flex-start
  border: 1px solid ${props => props.theme.colors.borderLight}
`

const AvatarSection = styled.div`
  display: flex
  flex-direction: column
  align-items: center
  gap: 1rem
`

const Avatar = styled.div`
  width: 80px
  height: 80px
  border-radius: 50%
  background: ${props => props.theme.colors.primary}
  color: white
  display: flex
  align-items: center
  justify-content: center
  font-weight: 600
  font-size: 1.5rem
`

const UserInfo = styled.div`
  flex: 1
  
  h1 {
    margin: 0 0 0.5rem 0
    color: ${props => props.theme.colors.textPrimary}
    font-size: 2rem
    font-weight: 600
  }
  
  .email {
    color: ${props => props.theme.colors.textSecondary}
    font-size: 1rem
    margin-bottom: 1rem
  }
  
  .joined {
    color: ${props => props.theme.colors.textTertiary}
    font-size: 0.9rem
  }
`

const EditButton = styled.button`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.5rem 1rem
  background: white
  color: ${props => props.theme.colors.primary}
  border: 2px solid ${props => props.theme.colors.primary}
  border-radius: 6px
  font-weight: 500
  cursor: pointer
  transition: all 0.2s
  
  &:hover {
    background: ${props => props.theme.colors.primary}
    color: white
  }
  
  .icon {
    width: 16px
    height: 16px
  }
`

const ProfileForm = styled.form`
  display: flex
  flex-direction: column
  gap: 1rem
  margin-top: 1rem
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

const Input = styled.input`
  padding: 0.75rem
  border: 2px solid ${props => props.theme.colors.border}
  border-radius: 6px
  font-size: 0.9rem
  transition: border-color 0.2s
  
  &:focus {
    outline: none
    border-color: ${props => props.theme.colors.primary}
  }
`

const FormActions = styled.div`
  display: flex
  gap: 0.5rem
`

const Button = styled.button<{ $variant?: 'primary' | 'secondary' }>`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.5rem 1rem
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
  
  .icon {
    width: 16px
    height: 16px
  }
`

const TabsContainer = styled.div`
  background: white
  border-radius: 12px
  overflow: hidden
  border: 1px solid ${props => props.theme.colors.borderLight}
`

const TabsList = styled.div`
  display: flex
  border-bottom: 1px solid ${props => props.theme.colors.borderLight}
`

const Tab = styled.button<{ $active: boolean }>`
  flex: 1
  display: flex
  align-items: center
  justify-content: center
  gap: 0.5rem
  padding: 1rem
  background: ${props => props.$active ? props.theme.colors.backgroundSecondary : 'white'}
  color: ${props => props.$active ? props.theme.colors.primary : props.theme.colors.textSecondary}
  border: none
  cursor: pointer
  font-weight: 500
  transition: all 0.2s
  
  &:hover {
    background: ${props => props.theme.colors.backgroundSecondary}
    color: ${props => props.theme.colors.primary}
  }
  
  .icon {
    width: 18px
    height: 18px
  }
`

const TabContent = styled.div`
  padding: 2rem
`

const StatsGrid = styled.div`
  display: grid
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))
  gap: 1rem
  margin-bottom: 2rem
`

const StatCard = styled.div`
  background: ${props => props.theme.colors.backgroundSecondary}
  padding: 1rem
  border-radius: 8px
  text-align: center
  
  .number {
    font-size: 1.5rem
    font-weight: 600
    color: ${props => props.theme.colors.primary}
    margin-bottom: 0.25rem
  }
  
  .label {
    font-size: 0.9rem
    color: ${props => props.theme.colors.textSecondary}
  }
`

const ItemsList = styled.div`
  display: flex
  flex-direction: column
  gap: 1rem
`

const ListItem = styled.div`
  background: ${props => props.theme.colors.backgroundSecondary}
  border-radius: 8px
  padding: 1rem
  display: flex
  justify-content: space-between
  align-items: flex-start
  
  .content {
    flex: 1
  }
  
  .title {
    font-weight: 500
    color: ${props => props.theme.colors.textPrimary}
    margin-bottom: 0.25rem
  }
  
  .description {
    font-size: 0.9rem
    color: ${props => props.theme.colors.textSecondary}
    margin-bottom: 0.5rem
  }
  
  .meta {
    font-size: 0.8rem
    color: ${props => props.theme.colors.textTertiary}
  }
`

const EmptyState = styled.div`
  text-align: center
  padding: 3rem 1rem
  color: ${props => props.theme.colors.textSecondary}
  
  .icon {
    width: 48px
    height: 48px
    margin: 0 auto 1rem
    opacity: 0.5
  }
  
  h3 {
    margin: 0 0 0.5rem 0
    color: ${props => props.theme.colors.textPrimary}
  }
`

const LoadingSpinner = styled.div`
  display: flex
  justify-content: center
  align-items: center
  padding: 2rem
  color: ${props => props.theme.colors.textSecondary}
`

type TabType = 'favorites' | 'comments' | 'missing-reports' | 'issue-reports' | 'settings'

export const ProfilePage: React.FC = () => {
  const { user, profile, updateProfile } = useAuth()
  const [activeTab, setActiveTab] = useState<TabType>('favorites')
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState({
    username: profile?.username || '',
    fullName: profile?.full_name || ''
  })

  // Data states
  const [favorites, setFavorites] = useState<BenchFavorite[]>([])
  const [comments, setComments] = useState<CommentWithProfile[]>([])
  const [missingReports, setMissingReports] = useState<MissingBenchReport[]>([])
  const [issueReports, setIssueReports] = useState<BenchIssueReport[]>([])
  const [loading, setLoading] = useState(false)

  // Load data based on active tab
  useEffect(() => {
    if (!user) return

    const loadData = async () => {
      setLoading(true)
      try {
        switch (activeTab) {
          case 'favorites':
            const favs = await FavoritesService.getFavorites(user.id)
            setFavorites(favs)
            break
          case 'comments':
            const comms = await CommentsService.getUserComments(user.id)
            setComments(comms)
            break
          case 'missing-reports':
            const missingReps = await MissingBenchService.getUserReports(user.id)
            setMissingReports(missingReps)
            break
          case 'issue-reports':
            const issueReps = await BenchIssueService.getUserReports(user.id)
            setIssueReports(issueReps)
            break
        }
      } catch (error) {
        console.error('Error loading data:', error)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [activeTab, user])

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await updateProfile({
        username: editForm.username.trim() || null,
        full_name: editForm.fullName.trim() || null
      })
      setIsEditing(false)
    } catch (error) {
      console.error('Error updating profile:', error)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
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

  if (!user) {
    return (
      <PageContainer>
        <Navigation />
        <Container>
          <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
            <h2>Please sign in to view your profile</h2>
          </div>
        </Container>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <Navigation />
      <Container>
        <Header>
          <AvatarSection>
            <Avatar>
              {profile?.avatar_url ? (
                <img 
                  src={profile.avatar_url} 
                  alt="Avatar" 
                  style={{ width: '100%', height: '100%', borderRadius: '50%' }}
                />
              ) : (
                getInitials(profile?.full_name || profile?.username, user.email)
              )}
            </Avatar>
          </AvatarSection>

          <UserInfo>
            {isEditing ? (
              <ProfileForm onSubmit={handleEditSubmit}>
                <InputGroup>
                  <Label>Full Name</Label>
                  <Input
                    value={editForm.fullName}
                    onChange={(e) => setEditForm(prev => ({ ...prev, fullName: e.target.value }))}
                    placeholder="Enter your full name"
                  />
                </InputGroup>
                <InputGroup>
                  <Label>Username</Label>
                  <Input
                    value={editForm.username}
                    onChange={(e) => setEditForm(prev => ({ ...prev, username: e.target.value }))}
                    placeholder="Enter a username"
                  />
                </InputGroup>
                <FormActions>
                  <Button type="submit" $variant="primary">
                    <Save className="icon" />
                    Save
                  </Button>
                  <Button type="button" onClick={() => setIsEditing(false)}>
                    <X className="icon" />
                    Cancel
                  </Button>
                </FormActions>
              </ProfileForm>
            ) : (
              <>
                <h1>
                  {profile?.full_name || profile?.username || 'User'}
                </h1>
                <div className="email">{user.email}</div>
                <div className="joined">
                  Joined {formatDate(profile?.created_at || user.created_at)}
                </div>
              </>
            )}
          </UserInfo>

          {!isEditing && (
            <EditButton onClick={() => {
              setEditForm({
                username: profile?.username || '',
                fullName: profile?.full_name || ''
              })
              setIsEditing(true)
            }}>
              <Edit className="icon" />
              Edit Profile
            </EditButton>
          )}
        </Header>

        <TabsContainer>
          <TabsList>
            <Tab
              $active={activeTab === 'favorites'}
              onClick={() => setActiveTab('favorites')}
            >
              <Heart className="icon" />
              Favorites ({favorites.length})
            </Tab>
            <Tab
              $active={activeTab === 'comments'}
              onClick={() => setActiveTab('comments')}
            >
              <MessageSquare className="icon" />
              Comments ({comments.length})
            </Tab>
            <Tab
              $active={activeTab === 'missing-reports'}
              onClick={() => setActiveTab('missing-reports')}
            >
              <MapPin className="icon" />
              Missing Reports ({missingReports.length})
            </Tab>
            <Tab
              $active={activeTab === 'issue-reports'}
              onClick={() => setActiveTab('issue-reports')}
            >
              <AlertTriangle className="icon" />
              Issue Reports ({issueReports.length})
            </Tab>
          </TabsList>

          <TabContent>
            {loading ? (
              <LoadingSpinner>Loading...</LoadingSpinner>
            ) : (
              <>
                {activeTab === 'favorites' && (
                  favorites.length > 0 ? (
                    <ItemsList>
                      {favorites.map((favorite) => (
                        <ListItem key={favorite.id}>
                          <div className="content">
                            <div className="title">Bench #{favorite.bench_id}</div>
                            <div className="meta">
                              Favorited on {formatDate(favorite.created_at)}
                            </div>
                          </div>
                        </ListItem>
                      ))}
                    </ItemsList>
                  ) : (
                    <EmptyState>
                      <Heart className="icon" />
                      <h3>No favorites yet</h3>
                      <p>Start exploring benches and save your favorites!</p>
                    </EmptyState>
                  )
                )}

                {activeTab === 'comments' && (
                  comments.length > 0 ? (
                    <ItemsList>
                      {comments.map((comment) => (
                        <ListItem key={comment.id}>
                          <div className="content">
                            <div className="title">Bench #{comment.bench_id}</div>
                            <div className="description">{comment.content}</div>
                            <div className="meta">
                              Posted on {formatDate(comment.created_at)}
                            </div>
                          </div>
                        </ListItem>
                      ))}
                    </ItemsList>
                  ) : (
                    <EmptyState>
                      <MessageSquare className="icon" />
                      <h3>No comments yet</h3>
                      <p>Share your thoughts about benches you've visited!</p>
                    </EmptyState>
                  )
                )}

                {activeTab === 'missing-reports' && (
                  missingReports.length > 0 ? (
                    <ItemsList>
                      {missingReports.map((report) => (
                        <ListItem key={report.id}>
                          <div className="content">
                            <div className="title">
                              Missing Bench Report ({report.lat.toFixed(4)}, {report.lng.toFixed(4)})
                            </div>
                            {report.description && (
                              <div className="description">{report.description}</div>
                            )}
                            <div className="meta">
                              Reported on {formatDate(report.created_at)} • Status: {report.status}
                            </div>
                          </div>
                        </ListItem>
                      ))}
                    </ItemsList>
                  ) : (
                    <EmptyState>
                      <MapPin className="icon" />
                      <h3>No missing bench reports</h3>
                      <p>Help improve our database by reporting missing benches!</p>
                    </EmptyState>
                  )
                )}

                {activeTab === 'issue-reports' && (
                  issueReports.length > 0 ? (
                    <ItemsList>
                      {issueReports.map((report) => (
                        <ListItem key={report.id}>
                          <div className="content">
                            <div className="title">
                              Bench #{report.bench_id} - {report.issue_type.replace('_', ' ').toUpperCase()}
                            </div>
                            <div className="description">{report.description}</div>
                            <div className="meta">
                              Reported on {formatDate(report.created_at)} • Status: {report.status}
                            </div>
                          </div>
                        </ListItem>
                      ))}
                    </ItemsList>
                  ) : (
                    <EmptyState>
                      <AlertTriangle className="icon" />
                      <h3>No issue reports</h3>
                      <p>Help keep our bench data accurate by reporting issues!</p>
                    </EmptyState>
                  )
                )}
              </>
            )}
          </TabContent>
        </TabsContainer>
      </Container>
    </PageContainer>
  )
}

export default ProfilePage