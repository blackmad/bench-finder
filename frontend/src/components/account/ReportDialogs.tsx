import { type FormEvent, lazy, type ReactNode, Suspense, useState } from "react"
import { api, unwrap, uploadPhoto } from "../../lib/api"
import { useAuth } from "../../lib/auth"
import { type PanoPick, parseStreetViewLink } from "../../lib/pano"
import {
  captureImage,
  getCurrentLocation,
  type ImageCaptureResult,
} from "../../utils/imageCapture"
import type { Point } from "./MapPicker"
import { Modal } from "./Modal"
import { Turnstile, turnstileSiteKey } from "./Turnstile"

const MapPicker = lazy(() => import("./MapPicker"))
const PanoPicker = lazy(() => import("./PanoPicker"))

export const REASONS = [
  ["not_a_bench", "There is no bench here, or it is not a bench"],
  ["wrong_location", "The pin is in the wrong place"],
  ["wrong_facing", "The facing, or what it looks out on, is wrong"],
  ["bad_image", "The photo is unusable"],
  ["other", "Something else"],
] as const
type Reason = (typeof REASONS)[number][0]

/** Shared form shell: optional photo, Turnstile for anonymous users, submit and result states. */
function ReportShell({
  title,
  intro,
  onClose,
  canSubmit,
  send,
  children,
}: {
  title: string
  intro: string
  onClose: () => void
  canSubmit: boolean
  send: (
    photoKey: string | undefined,
    token: string | undefined
  ) => Promise<void>
  children: ReactNode
}) {
  const { user, openSignIn } = useAuth()
  const [photo, setPhoto] = useState<ImageCaptureResult | null>(null)
  const [photoKey, setPhotoKey] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [resetKey, setResetKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const anonymous = !user

  const pickPhoto = async () => {
    try {
      const r = await captureImage({ maxWidth: 1600, maxHeight: 1600 })
      setPhoto(r)
      setPhotoKey(null)
    } catch {
      // cancelled
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)
    if (anonymous && turnstileSiteKey && !token) {
      setError("Please complete the spam check first.")
      return
    }
    setBusy(true)
    try {
      let key = photoKey
      let used = false
      if (photo && !key) {
        key = await uploadPhoto(photo.blob, token ?? undefined)
        setPhotoKey(key)
        used = true
        if (anonymous && turnstileSiteKey) {
          // Turnstile tokens are single use: ask for a fresh one for the report itself.
          setToken(null)
          setResetKey((n) => n + 1)
          setInfo("Photo uploaded. Complete the check once more, then send.")
          return
        }
      }
      await send(key ?? undefined, used ? undefined : (token ?? undefined))
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the report")
      if (anonymous && turnstileSiteKey) {
        setToken(null)
        setResetKey((n) => n + 1)
      }
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <Modal title={title} onClose={onClose}>
        <p role="status" className="form-ok">
          Thank you. A moderator will take a look.
        </p>
        <button type="button" className="btn" onClick={onClose}>
          Done
        </button>
      </Modal>
    )
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <p className="modal-lede">{intro}</p>
        {children}
        <div className="stack">
          <span className="caps">Photo (optional)</span>
          {photo ? (
            <div className="photo-pick">
              <img src={photo.dataUrl} alt="Your attached upload" />
              <button
                type="button"
                className="linkbtn"
                onClick={() => {
                  setPhoto(null)
                  setPhotoKey(null)
                }}
              >
                Remove
              </button>
            </div>
          ) : (
            <button type="button" className="btn" onClick={pickPhoto}>
              Add a photo
            </button>
          )}
        </div>
        {anonymous ? (
          <div className="stack">
            <Turnstile onToken={setToken} resetKey={resetKey} />
            <button type="button" className="linkbtn" onClick={openSignIn}>
              Or sign in to skip the check
            </button>
          </div>
        ) : null}
        {info ? (
          <p role="status" className="form-note">
            {info}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="form-error">
            {error}
          </p>
        ) : null}
        <div className="row">
          <button
            type="submit"
            className="btn primary"
            disabled={busy || !canSubmit}
          >
            {busy ? "Sending..." : "Send report"}
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function ReportBenchDialog({
  benchId,
  onClose,
}: {
  benchId: number
  onClose: () => void
}) {
  const [reason, setReason] = useState<Reason | null>(null)
  const [note, setNote] = useState("")
  return (
    <ReportShell
      title={`Report bench No. ${benchId}`}
      intro="What is wrong with this card?"
      onClose={onClose}
      canSubmit={reason !== null}
      send={async (photoKey, turnstileToken) => {
        if (!reason) return
        await unwrap(
          await api.api.reports.bench.$post({
            json: {
              benchId,
              reason,
              note: note.trim() || undefined,
              photoKey,
              turnstileToken,
            },
          })
        )
      }}
    >
      <fieldset className="reasons">
        <legend className="caps">Reason</legend>
        {REASONS.map(([value, label]) => (
          <label key={value} className="radio">
            <input
              type="radio"
              name="reason"
              value={value}
              checked={reason === value}
              onChange={() => setReason(value)}
            />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>
      <label className="stack" htmlFor="report-note">
        <span className="caps">Note (optional)</span>
        <textarea
          id="report-note"
          rows={3}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
    </ReportShell>
  )
}

export function MissingBenchDialog({
  center,
  onClose,
}: {
  /** Where the map is centred (or the bench being viewed). */
  center: Point
  onClose: () => void
}) {
  const [point, setPoint] = useState<Point>(center)
  const [accuracy, setAccuracy] = useState<number | undefined>()
  const [note, setNote] = useState("")
  const [locError, setLocError] = useState<string | null>(null)
  const [picking, setPicking] = useState(false)
  const [cityPick, setCityPick] = useState<PanoPick | null>(null)
  const [link, setLink] = useState("")
  const linked = link.trim() ? parseStreetViewLink(link) : null
  // A pasted link wins over the city panorama.
  const pano = linked
    ? {
        source: linked.source,
        id: linked.id,
        heading: linked.heading,
        url: linked.url,
      }
    : picking
      ? cityPick
      : null

  const locate = async () => {
    setLocError(null)
    try {
      const l = await getCurrentLocation()
      setPoint({ lat: l.lat, lng: l.lng })
      setAccuracy(l.accuracy)
    } catch (e) {
      setLocError(e instanceof Error ? e.message : "Could not get location")
    }
  }

  return (
    <ReportShell
      title="Report a missing bench"
      intro="Know a bench that is not on the map? Put the pin where it stands."
      onClose={onClose}
      canSubmit={!link.trim() || linked !== null}
      send={async (photoKey, turnstileToken) => {
        await unwrap(
          await api.api.reports.missing.$post({
            json: {
              lat: point.lat,
              lng: point.lng,
              accuracyMeters:
                accuracy === undefined ? undefined : Math.round(accuracy),
              pano: pano ?? undefined,
              note: note.trim() || undefined,
              photoKey,
              turnstileToken,
            },
          })
        )
      }}
    >
      <Suspense fallback={<div className="pickmap" />}>
        <MapPicker
          point={point}
          onChange={(p) => {
            setPoint(p)
            setAccuracy(undefined)
          }}
        />
      </Suspense>
      <div className="row">
        <span className="num coords">
          {point.lat.toFixed(5)}, {point.lng.toFixed(5)}
        </span>
        <button type="button" className="linkbtn" onClick={locate}>
          Use my location
        </button>
      </div>
      {locError ? (
        <p role="alert" className="form-error">
          {locError}
        </p>
      ) : null}
      <div className="stack">
        <span className="caps">Show us in a street panorama (optional)</span>
        {picking ? (
          <>
            <Suspense fallback={<p className="form-note">Loading…</p>}>
              <PanoPicker point={point} onChange={setCityPick} />
            </Suspense>
            <button
              type="button"
              className="linkbtn"
              onClick={() => {
                setPicking(false)
                setCityPick(null)
              }}
            >
              Remove the panorama
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn"
            onClick={() => setPicking(true)}
          >
            Find it in a panorama
          </button>
        )}
        <label className="stack" htmlFor="missing-link">
          <span className="form-note">
            Or paste a Google Street View link, looking at the bench
          </span>
          <input
            id="missing-link"
            type="url"
            inputMode="url"
            placeholder="https://www.google.com/maps/@52.36…"
            value={link}
            onChange={(e) => setLink(e.target.value)}
          />
        </label>
        {link.trim() ? (
          linked ? (
            <p className="form-ok" role="status">
              Street View link read: looking {Math.round(linked.heading)}°.
            </p>
          ) : (
            <p className="form-error" role="alert">
              That does not look like a Street View link. Open Street View, turn
              to the bench, and copy the address bar.
            </p>
          )
        ) : null}
      </div>
      <label className="stack" htmlFor="missing-note">
        <span className="caps">Note (optional)</span>
        <textarea
          id="missing-note"
          rows={2}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
    </ReportShell>
  )
}
