import { Link } from "react-router-dom"
import { focusStyle } from "../data/api"
import { headline, seatText } from "../data/describe"
import { looksAt } from "../data/facing"
import type { BenchProps } from "../data/types"
import { Away } from "./Away"
import { Photo } from "./Photo"

interface Props {
  bench: BenchProps
  selected?: boolean
  onSelect?: (id: number) => void
  /** Open the bench in the rail preview instead of following the link. */
  onOpen?: (id: number) => void
}

/** What the bench looks at ("Looks out over the water"), else its seat. */
export function caption(bench: BenchProps) {
  const looks = looksAt(bench.faces_category)
  if (looks) {
    return (
      <span className="looks" data-cat={bench.faces_category ?? undefined}>
        {looks}
      </span>
    )
  }
  return seatText(bench.backrest) ?? "Seat not recorded"
}

/** A photo tile on the rail: the view, its compass seal, the address. */
export function Tile({ bench, selected = false, onSelect, onOpen }: Props) {
  const name = headline(bench)
  return (
    <Link
      className="tile"
      to={`/?bench=${bench.id}`}
      data-id={bench.id}
      aria-current={selected ? "true" : undefined}
      onClick={
        onOpen
          ? (e) => {
              // A plain click opens the preview; new-tab clicks keep the link.
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
              e.preventDefault()
              onOpen(bench.id)
            }
          : undefined
      }
      onPointerEnter={onSelect ? () => onSelect(bench.id) : undefined}
      onFocus={onSelect ? () => onSelect(bench.id) : undefined}
    >
      <div className="ph">
        <Photo
          urls={bench.hero_urls}
          webp={bench.hero_urls_webp}
          sizes="(max-width: 760px) 70vw, 240px"
          alt={`Street view of the bench at ${name}`}
          width={bench.hero_width ?? 800}
          height={bench.hero_height ?? 800}
          style={focusStyle(bench.hero_focus)}
          loading="lazy"
          decoding="async"
        />
        <Away lat={bench.lat} lng={bench.lng} />
      </div>
      <div className="cap">
        <span className="caps">{name}</span>
        <small>{caption(bench)}</small>
      </div>
    </Link>
  )
}
