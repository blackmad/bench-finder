import { useId, useState } from "react"
import { ALL_MAX, type Row, STRIP_MAX } from "../data/rows"
import { Tile } from "./Tile"

interface Props {
  row: Row
  selectedId: number | null
  onSelect?: (id: number) => void
  /** Shown instead of the bench count, e.g. "within 1 km". */
  countLabel?: string
}

/** One titled row of photo tiles that scrolls sideways; "See all" wraps it. */
export function RailRow({ row, selectedId, onSelect, countLabel }: Props) {
  const [all, setAll] = useState(false)
  const id = useId()
  const shown = row.benches.slice(0, all ? ALL_MAX : STRIP_MAX)
  const more = row.benches.length > STRIP_MAX
  const n = row.benches.length
  return (
    <section
      className="railrow"
      aria-labelledby={id}
      data-all={all || undefined}
    >
      <div className="rowhead">
        <h3 id={id} className="caps">
          {row.title}
        </h3>
        <small>
          <span className="num">
            {countLabel ?? `${n.toLocaleString("en")} in view`}
          </span>
          {row.note ? <span className="note"> · {row.note}</span> : null}
        </small>
        {more ? (
          <button
            type="button"
            className="more"
            aria-expanded={all}
            onClick={() => setAll((a) => !a)}
          >
            {all ? "Show fewer" : n > ALL_MAX ? "See more" : "See all"}
          </button>
        ) : null}
      </div>
      <div className="strip">
        {shown.map((b) => (
          <Tile
            key={b.properties.id}
            bench={b.properties}
            selected={b.properties.id === selectedId}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  )
}
