import { Link } from "react-router-dom"
import { bestUrl, srcSet } from "../data/api"
import { facesText, isKnown, windName } from "../data/facing"
import type { BenchProps } from "../data/types"
import { Stamp } from "./postmark/Stamp"

const seatLabel = (p: BenchProps) =>
  p.bench_type === "backrest"
    ? "Backrest"
    : p.bench_type === "backless"
      ? "No backrest"
      : "Seat type unknown"

interface Props {
  bench: BenchProps
  selected: boolean
  onSelect: (id: number) => void
}

export function Postcard({ bench, selected, onSelect }: Props) {
  const street = bench.address ?? "Unnamed path"
  return (
    <Link
      className="postcard"
      to={`/bench/${bench.id}`}
      data-id={bench.id}
      aria-current={selected ? "true" : undefined}
      onPointerEnter={() => onSelect(bench.id)}
    >
      <div className="photo">
        <img
          src={bestUrl(bench.hero_urls)}
          srcSet={srcSet(bench.hero_urls)}
          sizes="(max-width: 760px) 76vw, 40vw"
          alt={`Bench on ${street}, looking toward ${facesText(bench.faces_category)}`}
          width={960}
          height={640}
          loading="lazy"
          decoding="async"
        />
      </div>
      <div className="stampslot">
        <Stamp bench={bench} selected={selected} />
      </div>
      <div className="caption">
        <span className="caps">{street}</span>
        <span className="serial">No.&nbsp;{bench.id}</span>
      </div>
      <div className="meta">
        <span>Looks at {facesText(bench.faces_category)}</span>
        <span>{seatLabel(bench)}</span>
      </div>
    </Link>
  )
}

/** Unphotographed bench: honest about the missing photo. */
export function PlainRow({ bench }: { bench: BenchProps }) {
  const known = isKnown(bench)
  const f = bench.facing
  return (
    <Link className="plain" to={`/bench/${bench.id}`} data-id={bench.id}>
      <svg viewBox="-20 -20 40 40" width="40" height="40" aria-hidden="true">
        <circle r="15" fill="none" stroke="var(--color-rule)" />
        {f === null ? null : (
          <g
            transform={`rotate(${f})`}
            stroke={known ? "var(--color-ink)" : "var(--color-airmail)"}
            strokeDasharray={known ? undefined : "2 2"}
            strokeWidth={known ? 2 : 1.2}
            fill="none"
          >
            <line y1="4" y2="-12" />
            <path d="M0 -15 l-3 5 h6z" />
          </g>
        )}
      </svg>
      <span>
        <span className="caps">{bench.address ?? "Unnamed path"}</span>
        <br />
        <small>
          {f === null
            ? "Facing not known"
            : `${known ? "Faces" : "Probably faces"} ${windName(f)}`}{" "}
          · no photo yet
        </small>
      </span>
      <span className="serial">No.&nbsp;{bench.id}</span>
    </Link>
  )
}
