/** What the signed-in user marked a bench as (drawn as a badge on the map). */
export type Mark = "fav" | "want" | "both"

/** Bench id -> badge, from the user's favourite and want-to-sit lists. */
export function marksFrom(
  me: { favorites: number[]; want?: number[] } | null | undefined
): Map<number, Mark> {
  const m = new Map<number, Mark>()
  for (const id of me?.favorites ?? []) m.set(id, "fav")
  for (const id of me?.want ?? []) m.set(id, m.has(id) ? "both" : "want")
  return m
}
