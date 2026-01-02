import type { User } from "firebase/auth"
import {
  signOut as firebaseSignOut,
  onAuthStateChanged,
  signInWithPopup,
} from "firebase/auth"
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import {
  type AuthProviderType,
  auth,
  authProviders,
} from "../services/firebase"

interface AuthContextType {
  user: User | null
  loading: boolean
  signInWithProvider: (
    provider: AuthProviderType
  ) => Promise<{ error: Error | null }>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth) {
      setLoading(false)
      return
    }

    // Listen for auth state changes
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user)
      setLoading(false)
    })

    return () => unsubscribe()
  }, [])

  const signInWithProvider = async (provider: AuthProviderType) => {
    if (!auth) {
      return { error: new Error("Firebase auth not initialized") }
    }

    try {
      const authProvider = authProviders[provider]
      await signInWithPopup(auth, authProvider)
      return { error: null }
    } catch (error) {
      console.error(`Failed to sign in with ${provider}:`, error)
      return { error: error as Error }
    }
  }

  const signOut = async () => {
    if (!auth) return
    await firebaseSignOut(auth)
  }

  const getAccessToken = async (): Promise<string | null> => {
    if (!user) return null
    try {
      return await user.getIdToken()
    } catch {
      return null
    }
  }

  const value = {
    user,
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
