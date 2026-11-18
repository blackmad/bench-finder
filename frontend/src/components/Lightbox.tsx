import { type KeyboardEvent, type TouchEvent, useEffect, useRef } from "react"
import type { GalleryImage } from "../data/types"
import { useSwipe } from "../lib/useSwipe"
import { Photo } from "./Photo"
import { lookText, photoDate } from "./ViewFigure"

interface Props {
  images: GalleryImage[]
  index: number
  /** The bench's headline, for the alt text. */
  name: string
  onIndex: (i: number) => void
  onClose: () => void
}

/**
 * One street view large, in a native modal <dialog>: Esc closes (the
 * browser's own), left/right arrows step through the views, a click on the
 * backdrop closes.
 */
export function Lightbox({ images, index, name, onIndex, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  const opener = useRef<HTMLElement | null>(
    document.activeElement as HTMLElement | null
  )

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => {
      queueMicrotask(() => {
        if (!dialog?.isConnected && opener.current?.isConnected) {
          opener.current.focus()
        }
      })
    }
  }, [])

  const n = images.length
  const step = (d: 1 | -1) => onIndex((index + d + n) % n)
  const swipe = useSwipe(n > 1 ? step : undefined)
  const g = images[index]
  if (!g) return null
  const onKey = (e: KeyboardEvent<HTMLDialogElement>) => {
    // The dialog sits inside pages that step benches on keys and swipes.
    e.stopPropagation()
    if (n < 2) return
    if (e.key === "ArrowRight") {
      e.preventDefault()
      step(1)
    } else if (e.key === "ArrowLeft") {
      e.preventDefault()
      step(-1)
    }
  }
  const look = lookText(g.heading)

  return (
    <dialog
      ref={ref}
      className="lightbox"
      aria-label={`Street view ${index + 1} of ${n}`}
      onClose={() => closeRef.current()}
      onKeyDown={onKey}
      onTouchStart={(e: TouchEvent) => {
        e.stopPropagation()
        swipe.onTouchStart?.(e)
      }}
      onTouchEnd={(e: TouchEvent) => {
        e.stopPropagation()
        swipe.onTouchEnd?.(e)
      }}
      onClick={(e) => {
        // The dialog element itself is only hit on the backdrop.
        if (e.target === e.currentTarget) ref.current?.close()
      }}
    >
      <figure>
        <Photo
          key={index}
          urls={g.urls}
          webp={g.urls_webp}
          sizes="100vw"
          alt={`Street view near the bench at ${name}, ${look.toLowerCase()}`}
          width={g.width}
          height={g.height}
          decoding="async"
        />
        <figcaption>
          <span>
            {look}
            {g.pano_date ? (
              <span className="when"> · {photoDate(g.pano_date)}</span>
            ) : null}
          </span>
          {n > 1 ? (
            <span className="num">
              {index + 1} / {n}
            </span>
          ) : null}
        </figcaption>
      </figure>
      {n > 1 ? (
        <>
          <button
            type="button"
            className="lb-step lb-prev"
            aria-label="Previous view"
            onClick={() => step(-1)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M15 5l-7 7 7 7" />
            </svg>
          </button>
          <button
            type="button"
            className="lb-step lb-next"
            aria-label="Next view"
            onClick={() => step(1)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </>
      ) : null}
      <button
        type="button"
        className="lb-x"
        aria-label="Close"
        onClick={() => ref.current?.close()}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      </button>
    </dialog>
  )
}
