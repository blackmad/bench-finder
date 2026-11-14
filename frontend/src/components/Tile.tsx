import { Link } from "react-router-dom"
import { headline, seatText } from "../data/describe"
import { facingKind, facingShort } from "../data/facing"
import type { BenchProps } from "../data/types"
import { Photo } from "./Photo"
import { Seal } from "./Seal"

interface Props {
  bench: BenchProps
  selected?: boolean
  onSelect?: (id: number) => void
}

/** "≈ Faces NE 52° · estimated · Backrest", leaving out what is not known. */
function caption(bench: BenchProps) {
  const facing = facingShort(bench)
  const kind = facingKind(bench)
  const seat = seatText(bench.backrest)
  if (!facing) return seat ?? "Seat not recorded"
  const est = kind === "estimated"
  return (
    <>
      <span className={est ? "est" : undefined}>
        {est ? "≈ " : ""}Faces {facing.replace(/^≈ /, "")} ·{" "}
        {est ? "estimated" : "mapped"}
      </span>
      {seat ? ` · ${seat}` : null}
    </>
  )
}

/** A photo tile on the rail: the view, its compass seal, the address. */
export function Tile({ bench, selected = false, onSelect }: Props) {
  const name = headline(bench)
  return (
    <Link
      className="tile"
      to={`/bench/${bench.id}`}
      data-id={bench.id}
      aria-current={selected ? "true" : undefined}
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
        <span className="sealslot">
          <Seal bench={bench} selected={selected} />
        </span>
      </div>
      <div className="cap">
        <span className="caps">{name}</span>
        <small>{caption(bench)}</small>
      </div>
    </Link>
  )
}
