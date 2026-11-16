import { Link } from "react-router-dom"
import { headline, seatText } from "../data/describe"
import { facingKind, facingShort, looksAt } from "../data/facing"
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

/**
 * "Looks out over the water · S 180°", else "≈ Faces NE 52° · estimated ·
 * Backrest", leaving out what is not known.
 */
export function caption(bench: BenchProps) {
  const facing = facingShort(bench)
  const kind = facingKind(bench)
  const seat = seatText(bench.backrest)
  const looks = looksAt(bench.faces_category)
  if (looks) {
    return (
      <>
        <span className="looks" data-cat={bench.faces_category ?? undefined}>
          {looks}
        </span>
        {facing ? (
          <span className={kind === "estimated" ? "est" : undefined}>
            {" "}
            · {facing}
          </span>
        ) : null}
      </>
    )
  }
  if (!facing) return seat ?? "Seat not recorded"
  const est = kind === "estimated"
  return (
    <>
      <span className={est ? "est" : undefined}>
        {est ? "≈ " : ""}Faces {facing.replace(/^≈ /, "")}
      </span>
      {seat ? ` · ${seat}` : null}
    </>
  )
}

/** A photo tile on the rail: the view, its compass seal, the address. */
export function Tile({ bench, selected = false, onSelect, onOpen }: Props) {
  const name = headline(bench)
  return (
    <Link
      className="tile"
      to={`/bench/${bench.id}`}
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
          loading="lazy"
          decoding="async"
        />
        <Away lat={bench.lat} lng={bench.lng} />
      </div>
      <div className="cap">
        <span className="caps">{name}</span>
        <small>
          {(bench.count ?? 1) > 1 ? (
            <span className="many">{bench.count} benches · </span>
          ) : null}
          {caption(bench)}
        </small>
      </div>
    </Link>
  )
}
