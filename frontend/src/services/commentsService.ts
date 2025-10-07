import { supabase } from '../lib/supabase'
import type { Database } from '../types/database'

type BenchComment = Database['public']['Tables']['bench_comments']['Row']
type NewBenchComment = Database['public']['Tables']['bench_comments']['Insert']
type UpdateBenchComment = Database['public']['Tables']['bench_comments']['Update']

export interface CommentWithProfile extends BenchComment {
  profiles: {
    username: string | null
    full_name: string | null
    avatar_url: string | null
  } | null
}

export class CommentsService {
  static async getComments(benchId: number): Promise<CommentWithProfile[]> {
    const { data, error } = await supabase
      .from('bench_comments')
      .select(`
        *,
        profiles:user_id (
          username,
          full_name,
          avatar_url
        )
      `)
      .eq('bench_id', benchId)
      .order('created_at', { ascending: true })

    if (error) {
      console.error('Error fetching comments:', error)
      throw new Error(error.message)
    }

    return data || []
  }

  static async addComment(userId: string, benchId: number, content: string): Promise<CommentWithProfile> {
    const comment: NewBenchComment = {
      user_id: userId,
      bench_id: benchId,
      content: content.trim()
    }

    const { data, error } = await supabase
      .from('bench_comments')
      .insert(comment)
      .select(`
        *,
        profiles:user_id (
          username,
          full_name,
          avatar_url
        )
      `)
      .single()

    if (error) {
      console.error('Error adding comment:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async updateComment(commentId: string, content: string): Promise<CommentWithProfile> {
    const update: UpdateBenchComment = {
      content: content.trim()
    }

    const { data, error } = await supabase
      .from('bench_comments')
      .update(update)
      .eq('id', commentId)
      .select(`
        *,
        profiles:user_id (
          username,
          full_name,
          avatar_url
        )
      `)
      .single()

    if (error) {
      console.error('Error updating comment:', error)
      throw new Error(error.message)
    }

    return data
  }

  static async deleteComment(commentId: string): Promise<void> {
    const { error } = await supabase
      .from('bench_comments')
      .delete()
      .eq('id', commentId)

    if (error) {
      console.error('Error deleting comment:', error)
      throw new Error(error.message)
    }
  }

  static async getUserComments(userId: string): Promise<CommentWithProfile[]> {
    const { data, error } = await supabase
      .from('bench_comments')
      .select(`
        *,
        profiles:user_id (
          username,
          full_name,
          avatar_url
        )
      `)
      .eq('user_id', userId)
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching user comments:', error)
      throw new Error(error.message)
    }

    return data || []
  }
}

export default CommentsService