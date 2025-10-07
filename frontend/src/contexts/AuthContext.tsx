import React, {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import type { User, Session, AuthError } from "@supabase/supabase-js"
import { supabase } from "../lib/supabase"
import type { Database } from "../types/database"

type Profile = Database['public']['Tables']['profiles']['Row']

interface AuthState {
  user: User | null
  profile: Profile | null
  session: Session | null
  loading: boolean
  error: AuthError | null
}

interface AuthContextType extends AuthState {
  signIn: (email: string, password: string) => Promise<{ error: AuthError | null }>
  signUp: (email: string, password: string, metadata?: { username?: string, full_name?: string }) => Promise<{ error: AuthError | null }>
  signInWithProvider: (provider: 'google' | 'github') => Promise<{ error: AuthError | null }>
  signOut: () => Promise<{ error: AuthError | null }>
  updateProfile: (updates: Partial<Profile>) => Promise<{ error: Error | null }>
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    profile: null,
    session: null,
    loading: true,
    error: null,
  })

  // Fetch user profile from Supabase
  const fetchProfile = async (userId: string): Promise<Profile | null> => {
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single()

      if (error) {
        console.error('Error fetching profile:', error)
        return null
      }

      return data
    } catch (error) {
      console.error('Error fetching profile:', error)
      return null
    }
  }

  // Initialize auth state
  useEffect(() => {
    let mounted = true

    const initializeAuth = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession()
        
        if (error) {
          console.error('Error getting session:', error)
          if (mounted) {
            setState(prev => ({
              ...prev,
              error,
              loading: false
            }))
          }
          return
        }

        let profile = null
        if (session?.user) {
          profile = await fetchProfile(session.user.id)
        }

        if (mounted) {
          setState({
            user: session?.user ?? null,
            profile,
            session,
            loading: false,
            error: null,
          })
        }
      } catch (error) {
        console.error('Error initializing auth:', error)
        if (mounted) {
          setState(prev => ({
            ...prev,
            error: error as AuthError,
            loading: false
          }))
        }
      }
    }

    initializeAuth()

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('Auth state change:', event, session?.user?.id)
        
        if (!mounted) return

        let profile = null
        if (session?.user) {
          profile = await fetchProfile(session.user.id)
        }

        setState({
          user: session?.user ?? null,
          profile,
          session,
          loading: false,
          error: null,
        })
      }
    )

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email: string, password: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    setState(prev => ({ ...prev, loading: false, error }))
    return { error }
  }

  const signUp = async (
    email: string, 
    password: string, 
    metadata?: { username?: string, full_name?: string }
  ) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: metadata || {}
      }
    })

    setState(prev => ({ ...prev, loading: false, error }))
    return { error }
  }

  const signInWithProvider = async (provider: 'google' | 'github') => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/auth/callback`
      }
    })

    setState(prev => ({ ...prev, loading: false, error }))
    return { error }
  }

  const signOut = async () => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    
    const { error } = await supabase.auth.signOut()
    
    setState(prev => ({ ...prev, loading: false, error }))
    return { error }
  }

  const updateProfile = async (updates: Partial<Profile>) => {
    if (!state.user) {
      return { error: new Error('No user logged in') }
    }

    setState(prev => ({ ...prev, loading: true }))

    try {
      const { error } = await supabase
        .from('profiles')
        .update(updates)
        .eq('id', state.user.id)

      if (error) {
        setState(prev => ({ ...prev, loading: false }))
        return { error: new Error(error.message) }
      }

      // Refresh profile data
      const updatedProfile = await fetchProfile(state.user.id)
      setState(prev => ({
        ...prev,
        profile: updatedProfile,
        loading: false
      }))

      return { error: null }
    } catch (error) {
      setState(prev => ({ ...prev, loading: false }))
      return { error: error as Error }
    }
  }

  const refreshProfile = async () => {
    if (!state.user) return

    const updatedProfile = await fetchProfile(state.user.id)
    setState(prev => ({
      ...prev,
      profile: updatedProfile
    }))
  }

  const contextValue: AuthContextType = {
    ...state,
    signIn,
    signUp,
    signInWithProvider,
    signOut,
    updateProfile,
    refreshProfile,
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

export default AuthContext