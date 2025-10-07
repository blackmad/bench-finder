import React, { useState } from 'react'
import styled from 'styled-components'
import { Heart } from 'lucide-react'
import { useFavorites } from '../hooks/useFavorites'
import { useAuth } from '../contexts/AuthContext'

interface FavoriteButtonProps {
  benchId: number
  size?: 'small' | 'medium' | 'large'
  variant?: 'icon' | 'button'
  className?: string
}

const Button = styled.button<{ 
  $size: 'small' | 'medium' | 'large'
  $variant: 'icon' | 'button'
  $isFavorite: boolean 
}>`
  display: flex
  align-items: center
  justify-content: center
  gap: ${props => props.$variant === 'button' ? '0.5rem' : '0'}
  background: ${props => props.$isFavorite 
    ? props.theme.colors.error
    : props.$variant === 'icon' ? 'rgba(255, 255, 255, 0.9)' : 'white'
  }
  color: ${props => props.$isFavorite 
    ? 'white'
    : props.theme.colors.textPrimary
  }
  border: 2px solid ${props => props.$isFavorite 
    ? props.theme.colors.error
    : props.theme.colors.border
  }
  border-radius: ${props => props.$variant === 'icon' ? '50%' : '8px'}
  cursor: pointer
  transition: all 0.2s
  font-weight: 500
  position: relative
  
  ${props => {
    const sizes = {
      small: { padding: '0.375rem', fontSize: '0.875rem', iconSize: 16 },
      medium: { padding: '0.5rem', fontSize: '0.9rem', iconSize: 18 },
      large: { padding: '0.75rem', fontSize: '1rem', iconSize: 20 }
    }
    const size = sizes[props.$size]
    return `
      padding: ${props.$variant === 'icon' ? size.padding : `${size.padding} ${props.$variant === 'button' ? '1rem' : size.padding}`};
      font-size: ${size.fontSize};
      
      .icon {
        width: ${size.iconSize}px;
        height: ${size.iconSize}px;
      }
    `
  }}
  
  &:hover {
    transform: scale(1.05)
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1)
    ${props => !props.$isFavorite && `
      border-color: ${props.theme.colors.error};
      color: ${props.theme.colors.error};
    `}
  }
  
  &:active {
    transform: scale(0.95)
  }
  
  &:disabled {
    opacity: 0.6
    cursor: not-allowed
    transform: none
  }
`

const LoadingSpinner = styled.div`
  width: 16px
  height: 16px
  border: 2px solid transparent
  border-top: 2px solid currentColor
  border-radius: 50%
  animation: spin 1s linear infinite
  
  @keyframes spin {
    0% { transform: rotate(0deg) }
    100% { transform: rotate(360deg) }
  }
`

const LoginPrompt = styled.div`
  position: absolute
  top: calc(100% + 0.5rem)
  left: 50%
  transform: translateX(-50%)
  background: ${props => props.theme.colors.textPrimary}
  color: white
  padding: 0.5rem 0.75rem
  border-radius: 6px
  font-size: 0.8rem
  white-space: nowrap
  z-index: 10
  opacity: 0
  visibility: hidden
  transition: all 0.2s
  pointer-events: none
  
  &::before {
    content: ''
    position: absolute
    top: -4px
    left: 50%
    transform: translateX(-50%)
    width: 0
    height: 0
    border-left: 4px solid transparent
    border-right: 4px solid transparent
    border-bottom: 4px solid ${props => props.theme.colors.textPrimary}
  }
`

const TooltipContainer = styled.div`
  position: relative
  
  &:hover ${LoginPrompt} {
    opacity: 1
    visibility: visible
  }
`

export const FavoriteButton: React.FC<FavoriteButtonProps> = ({
  benchId,
  size = 'medium',
  variant = 'icon',
  className
}) => {
  const { user } = useAuth()
  const { isFavorite, toggleFavorite, isLoggedIn } = useFavorites()
  const [isLoading, setIsLoading] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)

  const favorited = isFavorite(benchId)

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (!isLoggedIn) {
      setShowPrompt(true)
      setTimeout(() => setShowPrompt(false), 2000)
      return
    }

    try {
      setIsLoading(true)
      await toggleFavorite(benchId)
    } catch (error) {
      console.error('Failed to toggle favorite:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (!isLoggedIn && variant === 'icon') {
    return (
      <TooltipContainer className={className}>
        <Button
          $size={size}
          $variant={variant}
          $isFavorite={false}
          onClick={handleClick}
        >
          <Heart className="icon" />
          <LoginPrompt>Sign in to save favorites</LoginPrompt>
        </Button>
      </TooltipContainer>
    )
  }

  return (
    <Button
      $size={size}
      $variant={variant}
      $isFavorite={favorited}
      onClick={handleClick}
      disabled={isLoading}
      className={className}
      title={favorited ? 'Remove from favorites' : 'Add to favorites'}
    >
      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <Heart className="icon" fill={favorited ? 'currentColor' : 'none'} />
      )}
      {variant === 'button' && (
        <span>{favorited ? 'Favorited' : 'Add to Favorites'}</span>
      )}
    </Button>
  )
}

export default FavoriteButton