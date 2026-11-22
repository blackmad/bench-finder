import { bestUrl } from "../data/api"
import { windName } from "../data/facing"
import type { GalleryImage } from "../data/types"
import { Photo } from "./Photo"

/** "2026-04" -> "Apr 2026". */
export const photoDate = (ym: string) => {
  const [y, m] = ym.split("-").map(Number)
  if (!y) return ym
  return m
    ? new Date(y, m - 1).toLocaleDateString(undefined, {
        month: "short",
        year: "numeric",
      })
    : String(y)
}

/** "Looking NE · 45°", or that the heading is unknown. */
export const lookText = (h: number | null) =>
  h === null ? "Heading not recorded" : `Looking ${windName(h)} · ${h}°`

/**
 * One street view of a bench, captioned with where the camera looks and when.
 * The photo links to its full-size rendition; with `onOpen` a plain click
 * opens it in the page's lightbox instead.
 */
export function ViewFigure({
  image: g,
  name,
  sizes,
  onOpen,
  action,
}: {
  image: GalleryImage
  /** Shown under the caption, e.g. a lead photo button. */
  action?: React.ReactNode
  /** The bench's headline, for the alt text. */
  name: string
  sizes: string
  onOpen?: () => void
}) {
  const look = lookText(g.heading)
  const full = bestUrl(g.urls_webp ?? g.urls)
  return (
    <figure>
      <a
        className="viewlink"
        href={full}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => {
          // Modified clicks (new tab, etc.) keep the plain link behaviour.
          if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey || e.button)
            return
          e.preventDefault()
          onOpen()
        }}
      >
        <Photo
          urls={g.urls}
          webp={g.urls_webp}
          sizes={sizes}
          alt={`Street view near the bench at ${name}, ${look.toLowerCase()}`}
          width={g.width}
          height={g.height}
          loading="lazy"
          decoding="async"
        />
      </a>
      <figcaption>
        {look}
        {g.pano_date ? (
          <span className="when"> · {photoDate(g.pano_date)}</span>
        ) : null}
      </figcaption>
      {action}
    </figure>
  )
}
