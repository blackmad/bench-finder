import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { SignInDialog } from "../components/account/SignInDialog"
import { setTokenProvider } from "./api"
import { firebaseConfigured, loadFirebaseAuth } from "./firebase"

export interface AuthUser {
  uid: string
  name: string | null
  email: string | null
}

interface AuthContextValue {
  user: AuthUser | null
  /** False until we know whether a stored session exists. */
  ready: boolean
  configured: boolean
  openSignIn: () => void
  signInWithGoogle: () => Promise<void>
  sendEmailLink: (email: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const SESSION_FLAG = "bf:session"
const EMAIL_KEY = "bf:email"
const TEST_TOKEN_KEY = "bf:test-token"

function store(op: () => void) {
  try {
    op()
  } catch {
    // storage can be blocked
  }
}
function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

/** Dev only: a pre-minted token in localStorage stands in for Firebase (see worker AUTH_TEST_JWKS). */
function devTestUser(): { user: AuthUser; token: string } | null {
  if (!import.meta.env.DEV) return null
  const token = read(TEST_TOKEN_KEY)
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split(".")[1]))
    return {
      token,
      user: {
        uid: payload.sub,
        name: payload.name ?? null,
        email: payload.email ?? null,
      },
    }
  } catch {
    return null
  }
}

function maybeEmailLinkReturn(): boolean {
  return /[?&]oobCode=/.test(window.location.search)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [ready, setReady] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const authRef = useRef<Awaited<ReturnType<typeof loadFirebaseAuth>> | null>(
    null
  )
  const initRef = useRef<Promise<NonNullable<typeof authRef.current>> | null>(
    null
  )

  const init = useCallback(() => {
    initRef.current ??= (async () => {
      const fb = await loadFirebaseAuth()
      authRef.current = fb
      setTokenProvider(async () => {
        const u = fb.auth.currentUser
        return u ? u.getIdToken() : null
      })
      fb.mod.onAuthStateChanged(fb.auth, (u) => {
        setUser(u ? { uid: u.uid, name: u.displayName, email: u.email } : null)
        store(() =>
          u
            ? localStorage.setItem(SESSION_FLAG, "1")
            : localStorage.removeItem(SESSION_FLAG)
        )
        setReady(true)
      })
      if (fb.mod.isSignInWithEmailLink(fb.auth, window.location.href)) {
        const email =
          read(EMAIL_KEY) ??
          window.prompt("Confirm your email to finish signing in") ??
          ""
        if (email) {
          try {
            await fb.mod.signInWithEmailLink(
              fb.auth,
              email,
              window.location.href
            )
            store(() => localStorage.removeItem(EMAIL_KEY))
          } catch {
            // an expired link just leaves the user signed out
          }
        }
        window.history.replaceState(null, "", window.location.pathname)
      }
      return fb
    })()
    return initRef.current
  }, [])

  // Load Firebase at startup only when a session (or an email-link return) exists.
  useEffect(() => {
    const test = devTestUser()
    if (test) {
      setTokenProvider(async () => test.token)
      setUser(test.user)
      setReady(true)
      return
    }
    if (
      firebaseConfigured() &&
      (read(SESSION_FLAG) === "1" || maybeEmailLinkReturn())
    ) {
      init().catch(() => setReady(true))
    } else {
      setReady(true)
    }
  }, [init])

  // iOS Safari blocks a popup that is not opened synchronously inside the tap,
  // so Firebase is preloaded when the dialog opens and the popup call below
  // runs before any await. Only a tap made before the preload lands falls back
  // to awaiting it (and may still be blocked; a second tap then works).
  const signInWithGoogle = useCallback(async () => {
    const fb = authRef.current ?? (await init())
    const provider = new fb.mod.GoogleAuthProvider()
    await fb.mod.signInWithPopup(fb.auth, provider)
    setDialogOpen(false)
  }, [init])

  const openSignIn = useCallback(() => {
    setDialogOpen(true)
    if (firebaseConfigured()) init().catch(() => {})
  }, [init])

  const sendEmailLink = useCallback(
    async (email: string) => {
      const fb = await init()
      await fb.mod.sendSignInLinkToEmail(fb.auth, email, {
        url: `${window.location.origin}${window.location.pathname}`,
        handleCodeInApp: true,
      })
      store(() => localStorage.setItem(EMAIL_KEY, email))
    },
    [init]
  )

  const signOut = useCallback(async () => {
    if (devTestUser()) {
      store(() => localStorage.removeItem(TEST_TOKEN_KEY))
      window.location.reload()
      return
    }
    const fb = await init()
    await fb.mod.signOut(fb.auth)
  }, [init])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      configured: firebaseConfigured(),
      openSignIn,
      signInWithGoogle,
      sendEmailLink,
      signOut,
    }),
    [user, ready, openSignIn, signInWithGoogle, sendEmailLink, signOut]
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
      {dialogOpen && !user ? (
        <SignInDialog onClose={() => setDialogOpen(false)} />
      ) : null}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}
