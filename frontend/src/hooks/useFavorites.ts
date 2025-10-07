import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import FavoritesService from '../services/favoritesService'

export const useFavorites = () => {
  const { user } = useAuth()
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load favorites when user changes
  useEffect(() => {
    const loadFavorites = async () => {
      if (!user) {
        setFavoriteIds(new Set())
        return
      }

      try {
        setLoading(true)
        setError(null)
        const ids = await FavoritesService.getFavoriteIds(user.id)
        setFavoriteIds(new Set(ids))
      } catch (err) {
        setError('Failed to load favorites')
        console.error('Error loading favorites:', err)
      } finally {
        setLoading(false)
      }
    }

    loadFavorites()
  }, [user])

  const isFavorite = useCallback((benchId: number): boolean => {
    return favoriteIds.has(benchId)
  }, [favoriteIds])

  const toggleFavorite = useCallback(async (benchId: number): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to manage favorites')
    }

    try {
      setError(null)
      const wasFavorite = favoriteIds.has(benchId)
      
      // Optimistically update the UI
      setFavoriteIds(prev => {
        const newSet = new Set(prev)
        if (wasFavorite) {
          newSet.delete(benchId)
        } else {
          newSet.add(benchId)
        }
        return newSet
      })

      if (wasFavorite) {
        await FavoritesService.removeFavorite(user.id, benchId)
      } else {
        await FavoritesService.addFavorite(user.id, benchId)
      }
    } catch (err) {
      // Revert optimistic update on error
      setFavoriteIds(prev => {
        const newSet = new Set(prev)
        if (favoriteIds.has(benchId)) {
          newSet.add(benchId)
        } else {
          newSet.delete(benchId)
        }
        return newSet
      })
      setError('Failed to update favorite')
      console.error('Error toggling favorite:', err)
      throw err
    }
  }, [user, favoriteIds])

  const addFavorite = useCallback(async (benchId: number): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to add favorites')
    }

    if (favoriteIds.has(benchId)) {
      return // Already favorited
    }

    try {
      setError(null)
      setFavoriteIds(prev => new Set([...prev, benchId]))
      await FavoritesService.addFavorite(user.id, benchId)
    } catch (err) {
      // Revert optimistic update
      setFavoriteIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(benchId)
        return newSet
      })
      setError('Failed to add favorite')
      console.error('Error adding favorite:', err)
      throw err
    }
  }, [user, favoriteIds])

  const removeFavorite = useCallback(async (benchId: number): Promise<void> => {
    if (!user) {
      throw new Error('Must be logged in to remove favorites')
    }

    if (!favoriteIds.has(benchId)) {
      return // Not favorited
    }

    try {
      setError(null)
      setFavoriteIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(benchId)
        return newSet
      })
      await FavoritesService.removeFavorite(user.id, benchId)
    } catch (err) {
      // Revert optimistic update
      setFavoriteIds(prev => new Set([...prev, benchId]))
      setError('Failed to remove favorite')
      console.error('Error removing favorite:', err)
      throw err
    }
  }, [user, favoriteIds])

  return {
    favoriteIds: Array.from(favoriteIds),
    isFavorite,
    toggleFavorite,
    addFavorite,
    removeFavorite,
    loading,
    error,
    isLoggedIn: !!user
  }
}

export default useFavorites