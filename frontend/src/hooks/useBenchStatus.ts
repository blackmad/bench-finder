import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import BenchStatusService, { type StatusType } from '../services/benchStatusService'

export const useBenchStatus = (benchId: number) => {
  const { user } = useAuth()
  const [currentStatus, setCurrentStatus] = useState<StatusType | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusCounts, setStatusCounts] = useState<{
    want_to_go: number
    been_there: number
  }>({ want_to_go: 0, been_there: 0 })

  // Load current status and counts
  const loadStatus = useCallback(async () => {
    if (!benchId) return

    try {
      setLoading(true)
      setError(null)

      // Load user's status if logged in
      if (user) {
        const status = await BenchStatusService.getStatus(user.id, benchId)
        setCurrentStatus(status?.status || null)
      }

      // Load status counts for this bench
      const counts = await BenchStatusService.getBenchStatusCounts(benchId)
      setStatusCounts(counts)
    } catch (err) {
      setError('Failed to load bench status')
      console.error('Error loading bench status:', err)
    } finally {
      setLoading(false)
    }
  }, [benchId, user])

  // Load status when benchId or user changes
  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  const setStatus = useCallback(async (status: StatusType): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to set bench status')
    }

    try {
      setError(null)
      
      // Optimistically update the UI
      const previousStatus = currentStatus
      setCurrentStatus(status)
      
      // Update counts optimistically
      setStatusCounts(prev => {
        const newCounts = { ...prev }
        
        // Remove from previous status count
        if (previousStatus) {
          newCounts[previousStatus] = Math.max(0, newCounts[previousStatus] - 1)
        }
        
        // Add to new status count
        newCounts[status] = newCounts[status] + 1
        
        return newCounts
      })

      await BenchStatusService.setStatus(user.id, benchId, status)
    } catch (err) {
      // Revert optimistic update on error
      setCurrentStatus(currentStatus)
      await loadStatus() // Reload to ensure consistency
      
      setError('Failed to update bench status')
      console.error('Error setting bench status:', err)
      throw err
    }
  }, [user, benchId, currentStatus, loadStatus])

  const clearStatus = useCallback(async (): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to clear bench status')
    }

    try {
      setError(null)
      
      // Optimistically update the UI
      const previousStatus = currentStatus
      setCurrentStatus(null)
      
      // Update counts optimistically
      if (previousStatus) {
        setStatusCounts(prev => ({
          ...prev,
          [previousStatus]: Math.max(0, prev[previousStatus] - 1)
        }))
      }

      await BenchStatusService.clearStatus(user.id, benchId)
    } catch (err) {
      // Revert optimistic update on error
      setCurrentStatus(currentStatus)
      await loadStatus() // Reload to ensure consistency
      
      setError('Failed to clear bench status')
      console.error('Error clearing bench status:', err)
      throw err
    }
  }, [user, benchId, currentStatus, loadStatus])

  const toggleStatus = useCallback(async (status: StatusType): Promise<void> => {
    if (currentStatus === status) {
      await clearStatus()
    } else {
      await setStatus(status)
    }
  }, [currentStatus, setStatus, clearStatus])

  return {
    currentStatus,
    statusCounts,
    loading,
    error,
    setStatus,
    clearStatus,
    toggleStatus,
    refreshStatus: loadStatus,
    isLoggedIn: !!user,
    hasStatus: (status: StatusType) => currentStatus === status
  }
}

export default useBenchStatus