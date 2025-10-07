import { supabase } from '../lib/supabase'
import type { Database } from '../types/database'

type BenchIssueReport = Database['public']['Tables']['bench_issue_reports']['Row']
type NewBenchIssueReport = Database['public']['Tables']['bench_issue_reports']['Insert']

export type IssueType = 'damaged' | 'missing' | 'inappropriate' | 'other'
export type IssueStatus = 'pending' | 'resolved' | 'rejected'

export class BenchIssueService {
  static async reportIssue(
    userId: string,
    benchId: number,
    issueType: IssueType,
    description: string,
    imageUrl?: string
  ): Promise<BenchIssueReport> {
    const report: NewBenchIssueReport = {
      user_id: userId,
      bench_id: benchId,
      issue_type: issueType,
      description: description.trim(),
      image_url: imageUrl || null
    }

    const { data, error } = await supabase
      .from('bench_issue_reports')
      .insert(report)
      .select()
      .single()

    if (error) {
      console.error('Error reporting bench issue:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async getUserReports(userId: string): Promise<BenchIssueReport[]> {
    const { data, error } = await supabase
      .from('bench_issue_reports')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching user reports:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async getBenchReports(benchId: number): Promise<BenchIssueReport[]> {
    const { data, error } = await supabase
      .from('bench_issue_reports')
      .select('*')
      .eq('bench_id', benchId)
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching bench reports:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async getAllReports(status?: IssueStatus): Promise<BenchIssueReport[]> {
    let query = supabase
      .from('bench_issue_reports')
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
    status: IssueStatus
  ): Promise<BenchIssueReport> {
    const { data, error } = await supabase
      .from('bench_issue_reports')
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
      .from('bench_issue_reports')
      .delete()
      .eq('id', reportId)

    if (error) {
      console.error('Error deleting report:', error)
      throw new Error(error.message)
    }
  }
}

export default BenchIssueService