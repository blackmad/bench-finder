import React, { useState, useRef, useEffect } from 'react'
import styled from 'styled-components'
import { User, Settings, Heart, MessageSquare, MapPin, LogOut, ChevronDown } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

const MenuContainer = styled.div`
  position: relative
  display: inline-block
`

const MenuButton = styled.button`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.5rem 0.75rem
  background: white
  border: 2px solid ${props => props.theme.colors.border}
  border-radius: 8px
  cursor: pointer
  transition: all 0.2s
  font-size: 0.9rem
  
  &:hover {
    border-color: ${props => props.theme.colors.primary}
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1)
  }
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

const UserInfo = styled.div`
  display: flex
  flex-direction: column
  align-items: flex-start
  
  .name {
    font-weight: 500
    color: ${props => props.theme.colors.text.primary}
    line-height: 1
  }
  
  .email {
    font-size: 0.8rem
    color: ${props => props.theme.colors.text.secondary}
    line-height: 1
  }
`

const Dropdown = styled.div<{ isOpen: boolean }>`
  position: absolute
  top: calc(100% + 0.5rem)
  right: 0
  background: white
  border: 2px solid ${props => props.theme.colors.border}
  border-radius: 8px
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)
  min-width: 200px
  z-index: 50
  opacity: ${props => props.isOpen ? 1 : 0}
  visibility: ${props => props.isOpen ? 'visible' : 'hidden'}
  transform: ${props => props.isOpen ? 'translateY(0)' : 'translateY(-10px)'}
  transition: all 0.2s ease-in-out
`

const MenuItem = styled.button`
  width: 100%
  display: flex
  align-items: center
  gap: 0.75rem
  padding: 0.75rem 1rem
  background: none
  border: none
  cursor: pointer
  font-size: 0.9rem
  color: ${props => props.theme.colors.text.primary}
  transition: background-color 0.2s
  
  &:hover {
    background: ${props => props.theme.colors.background}
  }
  
  &:first-child {
    border-top-left-radius: 6px
    border-top-right-radius: 6px
  }
  
  &:last-child {
    border-bottom-left-radius: 6px
    border-bottom-right-radius: 6px
  }
  
  .icon {
    width: 18px
    height: 18px
    opacity: 0.7
  }
`

const Divider = styled.div`
  height: 1px
  background: ${props => props.theme.colors.border}
  margin: 0.25rem 0
`

export const UserMenu: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const { user, profile, signOut } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const handleSignOut = async () => {
    await signOut()
    setIsOpen(false)
  }

  if (!user) {
    return null
  }

  const getInitials = (name: string | null | undefined) => {
    if (!name) return user.email?.charAt(0).toUpperCase() || 'U'
    return name
      .split(' ')
      .map(part => part.charAt(0))
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const displayName = profile?.full_name || profile?.username || 'User'
  const initials = getInitials(displayName)

  return (
    <MenuContainer ref={menuRef}>
      <MenuButton onClick={() => setIsOpen(!isOpen)}>
        <Avatar>
          {profile?.avatar_url ? (
            <img 
              src={profile.avatar_url} 
              alt={displayName} 
              style={{ width: '100%', height: '100%', borderRadius: '50%' }}
            />
          ) : (
            initials
          )}
        </Avatar>
        <UserInfo>
          <div className="name">{displayName}</div>
          <div className="email">{user.email}</div>
        </UserInfo>
        <ChevronDown 
          size={16} 
          style={{ 
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s'
          }}
        />
      </MenuButton>

      <Dropdown isOpen={isOpen}>
        <MenuItem onClick={() => {
          navigate('/profile')
          setIsOpen(false)
        }}>
          <User className="icon" />
          Profile
        </MenuItem>
        
        <MenuItem onClick={() => setIsOpen(false)}>
          <Heart className="icon" />
          My Favorites
        </MenuItem>
        
        <MenuItem onClick={() => setIsOpen(false)}>
          <MessageSquare className="icon" />
          My Comments
        </MenuItem>
        
        <MenuItem onClick={() => setIsOpen(false)}>
          <MapPin className="icon" />
          My Reports
        </MenuItem>
        
        <Divider />
        
        <MenuItem onClick={() => setIsOpen(false)}>
          <Settings className="icon" />
          Settings
        </MenuItem>
        
        <MenuItem onClick={handleSignOut}>
          <LogOut className="icon" />
          Sign Out
        </MenuItem>
      </Dropdown>
    </MenuContainer>
  )
}

export default UserMenu