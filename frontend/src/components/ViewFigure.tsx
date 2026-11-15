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

/** One street view of a bench, captioned with where the camera looks and when. */
export function ViewFigure({
  image: g,
  name,
  sizes,
}: {
  image: GalleryImage
  /** The bench's headline, for the alt text. */
  name: string
  sizes: string
}) {
  const h = g.heading
  const look =
    h === null ? "Heading not recorded" : `Looking ${windName(h)} · ${h}°`
  return (
    <figure>
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
      <figcaption>
        {look}
        {g.pano_date ? (
          <span className="when"> · {photoDate(g.pano_date)}</span>
        ) : null}
      </figcaption>
    </figure>
  )
}
