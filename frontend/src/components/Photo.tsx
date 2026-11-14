import type { ImgHTMLAttributes } from "react"
import { bestUrl, srcSet } from "../data/api"
import type { ImageUrls } from "../data/types"

type Props = Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "srcSet"> & {
  /** AVIF renditions keyed by width. */
  urls: ImageUrls | null | undefined
  /** WebP renditions with the same widths, for browsers without AVIF. */
  webp?: ImageUrls | null
  sizes: string
}

/** A responsive photo: AVIF first, WebP fallback, explicit dimensions passed through. */
export function Photo({ urls, webp, sizes, alt, ...img }: Props) {
  if (!urls) return null
  const avifSet = srcSet(urls) ?? bestUrl(urls)
  const webpSet = webp ? (srcSet(webp) ?? bestUrl(webp)) : undefined
  return (
    <picture>
      <source type="image/avif" srcSet={avifSet} sizes={sizes} />
      {webpSet ? (
        <source type="image/webp" srcSet={webpSet} sizes={sizes} />
      ) : null}
      <img
        {...img}
        alt={alt}
        src={webp ? bestUrl(webp) : bestUrl(urls)}
        sizes={sizes}
      />
    </picture>
  )
}
