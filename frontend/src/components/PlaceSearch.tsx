import { useEffect, useId, useRef, useState } from "react"
import { SearchIcon } from "./Icons"

interface Place {
  key: string
  label: string
  detail: string
  center: [number, number]
}

interface PhotonFeature {
  geometry: { coordinates: [number, number] }
  properties: {
    osm_id?: number
    osm_type?: string
    name?: string
    street?: string
    housenumber?: string
    city?: string
    state?: string
    country?: string
  }
}

// Bias results toward the city the benches are in.
const BIAS = "lat=52.37&lon=4.89"

async function lookup(q: string, signal: AbortSignal): Promise<Place[]> {
  const res = await fetch(
    `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&${BIAS}&limit=5&lang=en`,
    { signal }
  )
  if (!res.ok) return []
  const data = (await res.json()) as { features?: PhotonFeature[] }
  const seen = new Set<string>()
  const places = (data.features ?? []).map((f, i) => {
    const p = f.properties
    const street = [p.street, p.housenumber].filter(Boolean).join(" ")
    const label = p.name ?? (street || "Unnamed place")
    const detail = [p.name ? street : "", p.city, p.country]
      .filter(Boolean)
      .join(", ")
    return {
      key: `${p.osm_type ?? ""}${p.osm_id ?? i}`,
      label,
      detail,
      center: f.geometry.coordinates,
    }
  })
  // Photon returns one hit per OSM object; show each name and area once.
  return places.filter((p) => {
    const k = `${p.label}|${p.detail}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}

interface Props {
  onPick: (center: [number, number]) => void
}

/** Place search (Photon): debounced, with a keyboard-operable results list. */
export function PlaceSearch({ onPick }: Props) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [status, setStatus] = useState("")
  const listId = useId()
  const wrap = useRef<HTMLFormElement>(null)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 3) {
      setResults([])
      setStatus("")
      return
    }
    const ctl = new AbortController()
    const t = window.setTimeout(async () => {
      try {
        const found = await lookup(q, ctl.signal)
        setResults(found)
        setActive(-1)
        setOpen(true)
        setStatus(
          found.length ? `${found.length} places found` : "No places found"
        )
      } catch {
        // Aborted by a newer keystroke, or offline: the map stays put.
      }
    }, 280)
    return () => {
      window.clearTimeout(t)
      ctl.abort()
    }
  }, [query])

  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("pointerdown", close)
    return () => document.removeEventListener("pointerdown", close)
  }, [])

  const pick = (p: Place) => {
    setQuery(p.label)
    setOpen(false)
    onPick(p.center)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" && results.length) {
      e.preventDefault()
      setOpen(true)
      setActive((a) => (a + 1) % results.length)
    } else if (e.key === "ArrowUp" && results.length) {
      e.preventDefault()
      setActive((a) => (a <= 0 ? results.length - 1 : a - 1))
    } else if (e.key === "Escape") {
      setOpen(false)
    }
  }

  const shown = open && results.length > 0
  return (
    // biome-ignore lint/a11y/useSemanticElements: <search> is not in the React 19 JSX types yet
    <form
      className="search"
      role="search"
      ref={wrap}
      onSubmit={(e) => {
        e.preventDefault()
        const p = results[active] ?? results[0]
        if (p) pick(p)
      }}
    >
      <label htmlFor="place-search" className="searchicon">
        <SearchIcon />
        <span className="sr">Search a place</span>
      </label>
      <input
        id="place-search"
        type="search"
        placeholder="Search a place"
        autoComplete="off"
        role="combobox"
        aria-expanded={shown}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        onKeyDown={onKeyDown}
      />
      <div className="results" id={listId} role="listbox" hidden={!shown}>
        {results.map((p, i) => (
          // biome-ignore lint/a11y/useKeyWithClickEvents: keyboard use goes through the combobox input
          <div
            key={p.key}
            id={`${listId}-${i}`}
            role="option"
            tabIndex={-1}
            aria-selected={i === active}
            data-active={i === active ? "" : undefined}
            onPointerDown={(e) => e.preventDefault()}
            onClick={() => pick(p)}
          >
            <b>{p.label}</b>
            {p.detail ? <small>{p.detail}</small> : null}
          </div>
        ))}
      </div>
      <span className="sr" role="status">
        {status}
      </span>
    </form>
  )
}
