import type { WebBenchData } from "../api/models/WebBenchData"

/**
 * Get the primary image URL for a bench.
 * Uses image_urls (Firebase Hosting URLs) when available,
 * otherwise falls back to constructing /images/{filename} URL.
 */
export function getBenchImageUrl(
  bench: WebBenchData,
  index: number = 0
): string | null {
  // Prefer image_urls (Firebase Hosting URLs) when available
  if (bench.image_urls && bench.image_urls.length > index) {
    return bench.image_urls[index]
  }

  // Fallback to constructing /images/{filename} URL
  if (bench.image_filenames && bench.image_filenames.length > index) {
    return `/images/${bench.image_filenames[index]}`
  }

  return null
}

/**
 * Get all image URLs for a bench.
 * Uses image_urls (Firebase Hosting URLs) when available,
 * otherwise constructs /images/{filename} URLs from filenames.
 */
export function getBenchImageUrls(bench: WebBenchData): string[] {
  // Prefer image_urls (Firebase Hosting URLs) when available
  if (bench.image_urls && bench.image_urls.length > 0) {
    return bench.image_urls
  }

  // Fallback to constructing /images/{filename} URLs
  if (bench.image_filenames && bench.image_filenames.length > 0) {
    return bench.image_filenames.map((filename) => `/images/${filename}`)
  }

  return []
}
