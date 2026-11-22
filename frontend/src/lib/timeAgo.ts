/** "just now", "5 min ago", "3 h ago", "2 days ago", else a short date. */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const s = Math.max(0, (now - new Date(iso).getTime()) / 1000)
  if (s < 60) return "just now"
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  const d = Math.floor(s / 86400)
  if (d < 7) return d === 1 ? "yesterday" : `${d} days ago`
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  })
}
