import { type FormEvent, useEffect, useRef, useState } from "react"
import { useMe, useUpdateProfile } from "../../data/social"
import { useAuth } from "../../lib/auth"
import {
  registerUsernameAsker,
  suggestUsername,
  usernameProblem,
} from "../../lib/username"
import { Modal } from "./Modal"

const ASKED = "bf:asked-username"

/**
 * Asks for a username: once after sign-in when there is none (skippable), and
 * whenever a post needs one (withUsername). Notes, photos and suggestions are
 * signed with it.
 */
export function UsernameDialog() {
  const { user } = useAuth()
  const me = useMe()
  const update = useUpdateProfile()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [problem, setProblem] = useState<string | null>(null)
  const pending = useRef<((ok: boolean) => void) | null>(null)

  useEffect(() => {
    registerUsernameAsker((resolve) => {
      pending.current?.(false)
      pending.current = resolve
      setOpen(true)
    })
    return () => registerUsernameAsker(null)
  }, [])

  const handle = me.data?.profile?.handle ?? null
  useEffect(() => {
    if (!user || !me.isSuccess || handle) return
    let asked = false
    try {
      asked = sessionStorage.getItem(`${ASKED}:${user.uid}`) === "1"
      sessionStorage.setItem(`${ASKED}:${user.uid}`, "1")
    } catch {
      // storage blocked: ask anyway
    }
    if (!asked) setOpen(true)
  }, [user, me.isSuccess, handle])

  useEffect(() => {
    if (open) setName((n) => n || suggestUsername(user?.name))
  }, [open, user?.name])

  if (!open || !user) return null

  const finish = (ok: boolean) => {
    setOpen(false)
    setProblem(null)
    pending.current?.(ok)
    pending.current = null
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const h = name.trim().toLowerCase()
    const p = usernameProblem(h)
    if (p) return setProblem(p)
    update.mutate(
      { handle: h },
      {
        onSuccess: () => finish(true),
        onError: (err) => setProblem(err.message),
      }
    )
  }

  return (
    <Modal title="Choose a username" onClose={() => finish(false)}>
      <p className="modal-lede">
        Your notes, photos and suggestions are shown with this name. It is also
        the address of your favourites page, if you make it public.
      </p>
      <form onSubmit={submit} className="stack" noValidate>
        <label htmlFor="username" className="caps">
          Username
        </label>
        <input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={24}
          placeholder="bench-lover"
          value={name}
          aria-invalid={problem ? true : undefined}
          aria-describedby={problem ? "username-problem" : undefined}
          onChange={(e) => {
            setName(e.target.value)
            setProblem(null)
          }}
        />
        {problem ? (
          <p id="username-problem" role="alert" className="form-error">
            {problem}
          </p>
        ) : null}
        <div className="row">
          <button
            type="submit"
            className="btn primary"
            disabled={update.isPending}
          >
            Save username
          </button>
          <button type="button" className="btn" onClick={() => finish(false)}>
            Not now
          </button>
        </div>
      </form>
    </Modal>
  )
}
