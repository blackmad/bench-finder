import React, { useState } from 'react'
import styled from 'styled-components'
import { MapPin, CheckCircle, Clock } from 'lucide-react'
import { useBenchStatus } from '../hooks/useBenchStatus'
import { useAuth } from '../contexts/AuthContext'
import type { StatusType } from '../services/benchStatusService'

interface BenchStatusButtonsProps {
  benchId: number
  layout?: 'horizontal' | 'vertical'
  showCounts?: boolean
  size?: 'small' | 'medium' | 'large'
  className?: string
}

const Container = styled.div<{ $layout: 'horizontal' | 'vertical' }>`
  display: flex
  gap: 0.5rem
  flex-direction: ${props => props.$layout === 'vertical' ? 'column' : 'row'}
`

const StatusButton = styled.button<{ 
  $active: boolean
  $variant: 'want_to_go' | 'been_there'
  $size: 'small' | 'medium' | 'large'
}>`
  display: flex
  align-items: center
  justify-content: center
  gap: 0.375rem
  border-radius: 6px
  font-weight: 500
  cursor: pointer
  transition: all 0.2s
  position: relative
  flex: 1
  
  ${props => {
    const sizes = {
      small: { padding: '0.375rem 0.75rem', fontSize: '0.8rem', iconSize: 14 },
      medium: { padding: '0.5rem 1rem', fontSize: '0.9rem', iconSize: 16 },
      large: { padding: '0.75rem 1.25rem', fontSize: '1rem', iconSize: 18 }
    }
    const size = sizes[props.$size]
    return `
      padding: ${size.padding};
      font-size: ${size.fontSize};
      
      .icon {
        width: ${size.iconSize}px;
        height: ${size.iconSize}px;
      }
    `
  }}
  
  ${props => {
    const colors = {
      want_to_go: {
        active: props.theme.colors.warning,
        activeHover: props.theme.colors.warningLight,
        inactive: 'white'
      },
      been_there: {
        active: props.theme.colors.success,
        activeHover: props.theme.colors.successLight,
        inactive: 'white'
      }
    }
    
    const color = colors[props.$variant]
    
    return props.$active ? `
      background: ${color.active};
      color: white;
      border: 2px solid ${color.active};
      
      &:hover {
        background: ${color.activeHover};
        border-color: ${color.activeHover};
      }
    ` : `
      background: ${color.inactive};
      color: ${props.theme.colors.textPrimary};
      border: 2px solid ${props.theme.colors.border};
      
      &:hover {
        border-color: ${color.active};
        color: ${color.active};
        background: ${props.theme.colors.backgroundSecondary};
      }
    `
  }}
  
  &:disabled {
    opacity: 0.6
    cursor: not-allowed
  }
`

const CountBadge = styled.span`
  position: absolute
  top: -6px
  right: -6px
  background: ${props => props.theme.colors.textPrimary}
  color: white
  font-size: 0.7rem
  font-weight: 600
  padding: 0.125rem 0.25rem
  border-radius: 10px
  min-width: 16px
  height: 16px
  display: flex
  align-items: center
  justify-content: center
  line-height: 1
`

const LoadingSpinner = styled.div`
  width: 14px
  height: 14px
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
  padding: 0.75rem 1rem
  background: ${props => props.theme.colors.backgroundSecondary}
  border: 2px dashed ${props => props.theme.colors.border}
  border-radius: 6px
  text-align: center
  color: ${props => props.theme.colors.textSecondary}
  font-size: 0.9rem
`

export const BenchStatusButtons: React.FC<BenchStatusButtonsProps> = ({
  benchId,
  layout = 'horizontal',
  showCounts = true,
  size = 'medium',
  className
}) => {
  const { user } = useAuth()
  const {
    currentStatus,
    statusCounts,
    loading,
    toggleStatus,
    isLoggedIn
  } = useBenchStatus(benchId)
  
  const [actionLoading, setActionLoading] = useState<StatusType | null>(null)

  const handleStatusClick = async (status: StatusType) => {
    if (!isLoggedIn) return

    try {
      setActionLoading(status)
      await toggleStatus(status)
    } catch (error) {
      console.error('Failed to update status:', error)
    } finally {
      setActionLoading(null)
    }
  }

  if (!isLoggedIn) {
    return (
      <LoginPrompt className={className}>
        Sign in to track your bench visits
      </LoginPrompt>
    )
  }

  return (
    <Container $layout={layout} className={className}>
      <StatusButton
        $active={currentStatus === 'want_to_go'}
        $variant="want_to_go"
        $size={size}
        onClick={() => handleStatusClick('want_to_go')}
        disabled={loading || actionLoading === 'want_to_go'}
        title="Mark as 'Want to go'"
      >
        {actionLoading === 'want_to_go' ? (
          <LoadingSpinner />
        ) : (
          <Clock className="icon" />
        )}
        Want to go
        {showCounts && statusCounts.want_to_go > 0 && (
          <CountBadge>{statusCounts.want_to_go}</CountBadge>
        )}
      </StatusButton>
      
      <StatusButton
        $active={currentStatus === 'been_there'}
        $variant="been_there"
        $size={size}
        onClick={() => handleStatusClick('been_there')}
        disabled={loading || actionLoading === 'been_there'}
        title="Mark as 'Been there'"
      >
        {actionLoading === 'been_there' ? (
          <LoadingSpinner />
        ) : (
          <CheckCircle className="icon" />
        )}
        Been there
        {showCounts && statusCounts.been_there > 0 && (
          <CountBadge>{statusCounts.been_there}</CountBadge>
        )}
      </StatusButton>
    </Container>
  )
}

export default BenchStatusButtons