/**
 * Words about a bench, built only from fields the published data carries.
 * Nothing here guesses: a missing field drops its clause, and the fallback
 * headline is the street address (or the bench number).
 */
import { facingKind, looksAt, WIND_LONG, windName } from "./facing"
import type { BenchDetail, BenchProps, GalleryImage } from "./types"

/** Plus codes ("9V5F+V2 Amsterdam") are not addresses a person would say. */
export const isStreetAddress = (a: string | null | undefined): a is string =>
  Boolean(a) && !/\+/.test(a as string)

/** "Kloveniersburgwal 143A" -> "Kloveniersburgwal". */
export const streetName = (a: string | null | undefined): string | null => {
  if (!isStreetAddress(a)) return null
  const s = a.replace(/\s+\d.*$/, "").trim()
  return s || null
}

export const headline = (b: Pick<BenchProps, "address" | "id">): string =>
  isStreetAddress(b.address) ? b.address : `Bench No. ${b.id}`

/** "1017 AE Amsterdam" -> "Amsterdam". */
export const cityName = (d: BenchDetail): string | null =>
  d.address_full.city?.replace(/^\d{4}\s?[A-Z]{2}\s+/, "").trim() || null

export const seatText = (backrest: boolean | null): string | null =>
  backrest === true ? "Backrest" : backrest === false ? "No backrest" : null

const NUMBERS = ["", "one", "two", "three", "four", "five", "six"]

/** "A wooden bench with a backrest, seats three, lit at night." */
export function bodySentence(d: BenchDetail): string {
  const t = d.tags ?? {}
  const material = d.material ?? t.material ?? null
  const adj: Record<string, string> = {
    wood: "wooden",
    metal: "metal",
    stone: "stone",
    concrete: "concrete",
    plastic: "plastic",
    steel: "steel",
  }
  const mat = material ? (adj[material] ?? material) : null
  const parts: string[] = []
  parts.push(
    `${mat ? `${/^[aeiou]/i.test(mat) ? "An" : "A"} ${mat}` : "A"} bench${
      d.backrest === true
        ? " with a backrest"
        : d.backrest === false
          ? " without a backrest"
          : ""
    }`
  )
  const seats = Number(t.seats)
  if (Number.isInteger(seats) && seats > 0) {
    parts.push(`seats ${NUMBERS[seats] ?? seats}`)
  }
  if (t.armrest === "yes") parts.push("armrests")
  if (t.lit === "yes") parts.push("lit at night")
  return `${parts.join(", ")}.`
}

/**
 * What the bench looks at leads ("Looks out over the water"); the compass
 * direction follows as the detail. Without a category it is the compass alone.
 */
export function facingSentence(
  p: Pick<BenchProps, "facing" | "facing_method" | "facing_confidence"> &
    Partial<Pick<BenchProps, "faces_category">>
): string | null {
  const looks = looksAt(p.faces_category)
  const k = facingKind(p)
  if (k === null || p.facing === null) return looks ? `${looks}.` : null
  const deg = Math.round(p.facing)
  const long = WIND_LONG[windName(deg)]
  if (looks) {
    return k === "mapped"
      ? `${looks}, facing ${long}.`
      : `${looks}, probably facing ${long}.`
  }
  if (k === "mapped") {
    return p.facing_method === "human"
      ? `Faces ${long}, confirmed by a visitor.`
      : `Faces ${long}, as mapped in OpenStreetMap.`
  }
  if (p.facing_method === "water_edge") {
    return `Probably faces ${long}, out over the water.`
  }
  if (p.facing_method === "water_back") {
    return `Probably faces ${long}, with the water behind it.`
  }
  const pct = Math.round((p.facing_confidence ?? 0) * 100)
  return `Probably faces ${long} (estimated from street views, ${pct}%).`
}

/** The gallery image the hero was cut from, found by its key in the URLs. */
export function heroImage(d: BenchDetail): GalleryImage | null {
  if (!d.hero_key) return null
  const key = d.hero_key
  return (
    d.gallery.find((g) => Object.values(g.urls).some((u) => u.includes(key))) ??
    null
  )
}

export function monthYear(ym: string | null | undefined): string | null {
  if (!ym) return null
  const [y, m] = ym.split("-").map(Number)
  if (!y) return null
  return m
    ? new Date(y, m - 1).toLocaleDateString("en", {
        month: "long",
        year: "numeric",
      })
    : String(y)
}

/**
 * Body + what it looks at + photo date, for the title cards. The compass
 * direction stays out: it means little to a visitor and the facts list has it.
 */
export function lede(d: BenchDetail): string {
  const hero = heroImage(d)
  const date = monthYear(hero?.pano_date)
  const looks = looksAt(d.faces_category) ?? d.faces_text ?? null
  // Without a photo every fact comes from the map data: say whose.
  const source = hero
    ? null
    : (d.tags ?? {}).source
      ? "As recorded by the City of Amsterdam."
      : "As mapped on OpenStreetMap."
  return [
    bodySentence(d),
    looks ? `${looks.replace(/\.$/, "")}.` : null,
    date ? `Photographed ${date}.` : null,
    source,
  ]
    .filter(Boolean)
    .join(" ")
}
