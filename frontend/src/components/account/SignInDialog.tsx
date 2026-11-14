import { type FormEvent, useState } from "react"
import { useAuth } from "../../lib/auth"
import { Modal } from "./Modal"

export function SignInDialog({ onClose }: { onClose: () => void }) {
  const { configured, signInWithGoogle, sendEmailLink } = useAuth()
  const [email, setEmail] = useState("")
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (op: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await op()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed")
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (email.trim())
      run(async () => {
        await sendEmailLink(email.trim())
        setSent(true)
      })
  }

  return (
    <Modal title="Sign in" onClose={onClose}>
      <p className="modal-lede">
        Browsing is open to everyone. Sign in to rate benches, keep your own
        lists and leave notes.
      </p>
      {configured ? (
        sent ? (
          <p role="status" className="form-ok">
            Check your inbox: we sent a sign-in link to {email}.
          </p>
        ) : (
          <>
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={() => run(signInWithGoogle)}
            >
              Continue with Google
            </button>
            <div className="or" aria-hidden="true">
              or
            </div>
            <form onSubmit={submit} className="stack">
              <label htmlFor="signin-email" className="caps">
                Email me a link
              </label>
              <input
                id="signin-email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <button type="submit" className="btn" disabled={busy}>
                Send sign-in link
              </button>
            </form>
          </>
        )
      ) : (
        <p className="form-note">
          Sign-in is not set up in this build. The site owner needs to provide
          the Firebase web config (VITE_FIREBASE_API_KEY and friends).
        </p>
      )}
      {error ? (
        <p role="alert" className="form-error">
          {error}
        </p>
      ) : null}
    </Modal>
  )
}
