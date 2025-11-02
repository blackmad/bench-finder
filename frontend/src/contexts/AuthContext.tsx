import type { Session, User } from "@supabase/supabase-js"
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import { supabase } from "../services/supabase"

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signInWithProvider: (
    provider: "google" | "github" | "apple" | "facebook"
  ) => Promise<{ error: Error | null }>
  signOut: () => Promise<void>
  getAccessToken: () => string | null
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signInWithProvider = async (
    provider: "google" | "github" | "apple" | "facebook"
  ) => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}${window.location.pathname}`,
      },
    })
    return { error }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  const getAccessToken = () => {
    return session?.access_token ?? null
  }

  const value = {
    user,
    session,
    loading,
    signInWithProvider,
    signOut,
    getAccessToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
