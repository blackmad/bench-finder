import { supabase } from '../lib/supabase'
import type { Database } from '../types/database'

type BenchFavorite = Database['public']['Tables']['bench_favorites']['Row']
type NewBenchFavorite = Database['public']['Tables']['bench_favorites']['Insert']

export class FavoritesService {
  static async getFavorites(userId: string): Promise<BenchFavorite[]> {
    const { data, error } = await supabase
      .from('bench_favorites')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching favorites:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async addFavorite(userId: string, benchId: number): Promise<BenchFavorite> {
    const favorite: NewBenchFavorite = {
      user_id: userId,
      bench_id: benchId
    }

    const { data, error } = await supabase
      .from('bench_favorites')
      .insert(favorite)
      .select()
      .single()

    if (error) {
      console.error('Error adding favorite:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async removeFavorite(userId: string, benchId: number): Promise<void> {
    const { error } = await supabase
      .from('bench_favorites')
      .delete()
      .eq('user_id', userId)
      .eq('bench_id', benchId)

    if (error) {
      console.error('Error removing favorite:', error)
      throw new Error(error.message)
    }
  }

  static async isFavorite(userId: string, benchId: number): Promise<boolean> {
    const { data, error } = await supabase
      .from('bench_favorites')
      .select('id')
      .eq('user_id', userId)
      .eq('bench_id', benchId)
      .single()

    if (error && error.code !== 'PGRST116') { // PGRST116 is "not found"
      console.error('Error checking favorite status:', error)
      throw new Error(error.message)
    }

    return !!data
  }

  static async getFavoriteIds(userId: string): Promise<number[]> {
    const { data, error } = await supabase
      .from('bench_favorites')
      .select('bench_id')
      .eq('user_id', userId)

    if (error) {
      console.error('Error fetching favorite IDs:', error)
      throw new Error(error.message)
    }

    return data?.map(item => item.bench_id) || []
  }
}

export default FavoritesService