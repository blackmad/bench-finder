import { supabase } from '../lib/supabase'
import type { Database } from '../types/database'

type BenchStatus = Database['public']['Tables']['bench_status']['Row']
type NewBenchStatus = Database['public']['Tables']['bench_status']['Insert']
type UpdateBenchStatus = Database['public']['Tables']['bench_status']['Update']

export type StatusType = 'want_to_go' | 'been_there'

export class BenchStatusService {
  static async getStatus(userId: string, benchId: number): Promise<BenchStatus | null> {
    const { data, error } = await supabase
      .from('bench_status')
      .select('*')
      .eq('user_id', userId)
      .eq('bench_id', benchId)
      .single()

    if (error && error.code !== 'PGRST116') { // PGRST116 is "not found"
      console.error('Error fetching bench status:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async setStatus(userId: string, benchId: number, status: StatusType): Promise<BenchStatus> {
    const statusData: NewBenchStatus = {
      user_id: userId,
      bench_id: benchId,
      status
    }

    // Use upsert to handle both insert and update cases
    const { data, error } = await supabase
      .from('bench_status')
      .upsert(statusData, {
        onConflict: 'user_id,bench_id'
      })
      .select()
      .single()

    if (error) {
      console.error('Error setting bench status:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async clearStatus(userId: string, benchId: number): Promise<void> {
    const { error } = await supabase
      .from('bench_status')
      .delete()
      .eq('user_id', userId)
      .eq('bench_id', benchId)

    if (error) {
      console.error('Error clearing bench status:', error)
      throw new Error(error.message)
    }
  }

  static async getUserStatuses(userId: string, statusType?: StatusType): Promise<BenchStatus[]> {
    let query = supabase
      .from('bench_status')
      .select('*')
      .eq('user_id', userId)
      .order('updated_at', { ascending: false })

    if (statusType) {
      query = query.eq('status', statusType)
    }

    const { data, error } = await query

    if (error) {
      console.error('Error fetching user statuses:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async getBenchStatusCounts(benchId: number): Promise<{
    want_to_go: number
    been_there: number
  }> {
    const [wantToGoResult, beenThereResult] = await Promise.all([
      supabase
        .from('bench_status')
        .select('id')
        .eq('bench_id', benchId)
        .eq('status', 'want_to_go'),
      supabase
        .from('bench_status')
        .select('id')
        .eq('bench_id', benchId)
        .eq('status', 'been_there')
    ])

    return {
      want_to_go: wantToGoResult.data?.length || 0,
      been_there: beenThereResult.data?.length || 0
    }
  }
}

export default BenchStatusService