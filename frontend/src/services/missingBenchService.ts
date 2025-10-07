import { supabase } from '../lib/supabase'
import type { Database } from '../types/database'

type MissingBenchReport = Database['public']['Tables']['missing_bench_reports']['Row']
type NewMissingBenchReport = Database['public']['Tables']['missing_bench_reports']['Insert']

export class MissingBenchService {
  static async reportMissingBench(
    userId: string,
    lat: number,
    lng: number,
    description?: string,
    imageUrl?: string
  ): Promise<MissingBenchReport> {
    const report: NewMissingBenchReport = {
      user_id: userId,
      lat,
      lng,
      description: description?.trim() || null,
      image_url: imageUrl || null
    }

    const { data, error } = await supabase
      .from('missing_bench_reports')
      .insert(report)
      .select()
      .single()

    if (error) {
      console.error('Error reporting missing bench:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async getUserReports(userId: string): Promise<MissingBenchReport[]> {
    const { data, error } = await supabase
      .from('missing_bench_reports')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching user reports:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async getAllReports(status?: 'pending' | 'approved' | 'rejected'): Promise<MissingBenchReport[]> {
    let query = supabase
      .from('missing_bench_reports')
      .select('*')
      .order('created_at', { ascending: false })

    if (status) {
      query = query.eq('status', status)
    }

    const { data, error } = await query

    if (error) {
      console.error('Error fetching reports:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async updateReportStatus(
    reportId: string,
    status: 'pending' | 'approved' | 'rejected'
  ): Promise<MissingBenchReport> {
    const { data, error } = await supabase
      .from('missing_bench_reports')
      .update({ status })
      .eq('id', reportId)
      .select()
      .single()

    if (error) {
      console.error('Error updating report status:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async deleteReport(reportId: string): Promise<void> {
    const { error } = await supabase
      .from('missing_bench_reports')
      .delete()
      .eq('id', reportId)

    if (error) {
      console.error('Error deleting report:', error)
      throw new Error(error.message)
    }
  }
}

export default MissingBenchService