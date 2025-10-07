import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import styled from 'styled-components'
import { Compass, Grid, Map, LogIn } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import AuthModal from './auth/AuthModal'
import UserMenu from './auth/UserMenu'

const Nav = styled.nav`
  background: white
  border-bottom: 2px solid ${props => props.theme.colors.border}
  padding: 1rem 0
  position: sticky
  top: 0
  z-index: 40
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1)
`

const NavContainer = styled.div`
  max-width: 1200px
  margin: 0 auto
  padding: 0 1rem
  display: flex
  justify-content: space-between
  align-items: center
`

const Logo = styled(Link)`
  display: flex
  align-items: center
  gap: 0.5rem
  text-decoration: none
  color: ${props => props.theme.colors.primary}
  font-weight: 600
  font-size: 1.25rem
  
  &:hover {
    color: ${props => props.theme.colors.primaryHover}
  }
`

const NavLinks = styled.div`
  display: flex
  gap: 1rem
  align-items: center
`

const NavLink = styled(Link)<{ $active: boolean }>`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.5rem 1rem
  border-radius: 8px
  text-decoration: none
  font-weight: 500
  transition: all 0.2s
  
  ${props => props.$active ? `
    background: ${props.theme.colors.primary};
    color: white;
  ` : `
    color: ${props.theme.colors.text.secondary};
    
    &:hover {
      background: ${props.theme.colors.background};
      color: ${props.theme.colors.text.primary};
    }
  `}
`

const AuthButton = styled.button`
  display: flex
  align-items: center
  gap: 0.5rem
  padding: 0.5rem 1rem
  background: ${props => props.theme.colors.primary}
  color: white
  border: none
  border-radius: 8px
  font-weight: 500
  cursor: pointer
  transition: background-color 0.2s
  
  &:hover {
    background: ${props => props.theme.colors.primaryHover}
  }
`

const AuthSection = styled.div`
  display: flex
  align-items: center
  gap: 1rem
`

const LoadingSpinner = styled.div`
  width: 20px
  height: 20px
  border: 2px solid ${props => props.theme.colors.border}
  border-top: 2px solid ${props => props.theme.colors.primary}
  border-radius: 50%
  animation: spin 1s linear infinite
  
  @keyframes spin {
    0% { transform: rotate(0deg) }
    100% { transform: rotate(360deg) }
  }
`

export const Navigation: React.FC = () => {
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)
  const location = useLocation()
  const { user, loading } = useAuth()

  const isActive = (path: string) => location.pathname === path

  return (
    <>
      <Nav>
        <NavContainer>
          <Logo to="/">
            <Compass size={28} />
            Bench Finder
          </Logo>
          
          <NavLinks>
            <NavLink to="/cards" $active={isActive('/cards')}>
              <Grid size={18} />
              Cards
            </NavLink>
            <NavLink to="/map" $active={isActive('/map')}>
              <Map size={18} />
              Map
            </NavLink>
          </NavLinks>

          <AuthSection>
            {loading ? (
              <LoadingSpinner />
            ) : user ? (
              <UserMenu />
            ) : (
              <AuthButton onClick={() => setIsAuthModalOpen(true)}>
                <LogIn size={18} />
                Sign In
              </AuthButton>
            )}
          </AuthSection>
        </NavContainer>
      </Nav>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initialMode="signin"
      />
    </>
  )
}

export default Navigation