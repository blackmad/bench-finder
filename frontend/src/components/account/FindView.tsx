import { useEffect, useRef, useState } from "react"
import { useSuggestView } from "../../data/heroes"
import type { StreetViewTarget } from "../../data/streetView"
import { useAuth } from "../../lib/auth"
import {
  loadGoogleMaps,
  type StreetViewPanorama,
  zoomToFov,
} from "../../lib/googleMaps"
import { Modal } from "./Modal"

/**
 * "Find a better view": a live Street View where you walk and look around,
 * then send the camera as a suggestion. It is rendered into a photo offline.
 */
export function FindView({
  benchId,
  target,
  onClose,
}: {
  benchId: number
  target: StreetViewTarget
  onClose: () => void
}) {
  const { user, openSignIn } = useAuth()
  const el = useRef<HTMLDivElement>(null)
  const pano = useRef<StreetViewPanorama | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const suggest = useSuggestView(benchId)

  useEffect(() => {
    let live = true
    loadGoogleMaps().then(
      (maps) => {
        if (!live || !el.current) return
        pano.current = new maps.StreetViewPanorama(el.current, {
          ...(target.pano
            ? { pano: target.pano }
            : target.at
              ? { position: { lat: target.at[0], lng: target.at[1] } }
              : {}),
          pov: { heading: target.heading, pitch: 0 },
          zoom: 1,
          addressControl: false,
          fullscreenControl: false,
          motionTracking: false,
          showRoadLabels: false,
        })
      },
      (e: Error) => live && setError(e.message)
    )
    return () => {
      live = false
    }
  }, [target])

  const send = () => {
    const p = pano.current
    if (!p) return
    if (!user) return openSignIn()
    const pov = p.getPov()
    suggest.mutate(
      {
        panoId: p.getPano(),
        heading: pov.heading,
        pitch: pov.pitch,
        fov: zoomToFov(p.getZoom()),
      },
      { onSuccess: () => setSent(true) }
    )
  }

  return (
    <Modal title="Find a better view" onClose={onClose}>
      <p className="hint">
        Walk along the street and turn until the bench and what it looks at are
        in frame, then send it. We render your view into a photo, and a
        moderator decides whether it leads.
      </p>
      <div ref={el} className="findview" />
      {error ? (
        <p role="alert" className="form-error">
          Street View could not load: {error}
        </p>
      ) : null}
      {suggest.error ? (
        <p role="alert" className="form-error">
          {suggest.error.message}
        </p>
      ) : null}
      <div className="row">
        {sent ? (
          <p className="hint">Sent, thank you. You can send another.</p>
        ) : null}
        <button
          type="button"
          className="btn primary"
          disabled={!!error || suggest.isPending}
          onClick={() => {
            setSent(false)
            send()
          }}
        >
          {user ? "Suggest this view" : "Sign in to suggest this view"}
        </button>
      </div>
    </Modal>
  )
}
