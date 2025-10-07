export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string
          username: string | null
          full_name: string | null
          avatar_url: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          username?: string | null
          full_name?: string | null
          avatar_url?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          username?: string | null
          full_name?: string | null
          avatar_url?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      bench_favorites: {
        Row: {
          id: string
          user_id: string
          bench_id: number
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          bench_id: number
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          bench_id?: number
          created_at?: string
        }
      }
      bench_comments: {
        Row: {
          id: string
          user_id: string
          bench_id: number
          content: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          bench_id: number
          content: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          bench_id?: number
          content?: string
          created_at?: string
          updated_at?: string
        }
      }
      bench_status: {
        Row: {
          id: string
          user_id: string
          bench_id: number
          status: 'want_to_go' | 'been_there'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          bench_id: number
          status: 'want_to_go' | 'been_there'
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          bench_id?: number
          status?: 'want_to_go' | 'been_there'
          created_at?: string
          updated_at?: string
        }
      }
      missing_bench_reports: {
        Row: {
          id: string
          user_id: string
          lat: number
          lng: number
          description: string | null
          image_url: string | null
          status: 'pending' | 'approved' | 'rejected'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          lat: number
          lng: number
          description?: string | null
          image_url?: string | null
          status?: 'pending' | 'approved' | 'rejected'
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          lat?: number
          lng?: number
          description?: string | null
          image_url?: string | null
          status?: 'pending' | 'approved' | 'rejected'
          created_at?: string
          updated_at?: string
        }
      }
      bench_issue_reports: {
        Row: {
          id: string
          user_id: string
          bench_id: number
          issue_type: 'damaged' | 'missing' | 'inappropriate' | 'other'
          description: string
          image_url: string | null
          status: 'pending' | 'resolved' | 'rejected'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          bench_id: number
          issue_type: 'damaged' | 'missing' | 'inappropriate' | 'other'
          description: string
          image_url?: string | null
          status?: 'pending' | 'resolved' | 'rejected'
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          bench_id?: number
          issue_type?: 'damaged' | 'missing' | 'inappropriate' | 'other'
          description?: string
          image_url?: string | null
          status?: 'pending' | 'resolved' | 'rejected'
          created_at?: string
          updated_at?: string
        }
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}