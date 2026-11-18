import { useEffect, useId, useRef, useState } from "react"
import { benchCount } from "../data/hooks"
import { ALL_MAX, type Row, STRIP_MAX } from "../data/rows"
import { Tile } from "./Tile"

interface Props {
  row: Row
  selectedId: number | null
  onSelect?: (id: number) => void
  onOpen?: (id: number) => void
  /** Shown instead of the bench count, e.g. "within 1 km". */
  countLabel?: string
  /** Headless and wrapped into a grid, growing by ALL_MAX ("Show more"). */
  grid?: boolean
}

/** One titled row of photo tiles that scrolls sideways; "See all" wraps it. */
export function RailRow({
  row,
  selectedId,
  onSelect,
  onOpen,
  countLabel,
  grid,
}: Props) {
  const [all, setAll] = useState(false)
  const [limit, setLimit] = useState(ALL_MAX)
  const id = useId()
  const sentinel = useRef<HTMLDivElement>(null)
  const shown = row.benches.slice(0, all ? ALL_MAX : STRIP_MAX)
  const more = row.benches.length > STRIP_MAX
  const n = row.benches.length
  // Each tile is a place; the count is of benches.
  const benches = row.benches.reduce((s, b) => s + benchCount(b.properties), 0)
  const hasMore = grid && n > limit
  // The grid grows by itself as its end scrolls into sight; the button below
  // stays for browsers without IntersectionObserver and for keyboard users.
  // `limit` re-arms the observer after each page, so a sentinel that is still
  // in sight (a tall rail) keeps loading until it is pushed out of view.
  // biome-ignore lint/correctness/useExhaustiveDependencies: see above
  useEffect(() => {
    const el = sentinel.current
    if (!hasMore || !el || typeof IntersectionObserver === "undefined") return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setLimit((l) => l + ALL_MAX)
        }
      },
      { rootMargin: "0px 0px 600px 0px" }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [hasMore, limit])
  if (grid)
    return (
      <section className="railrow" data-all aria-label="Benches in view">
        <div className="strip">
          {row.benches.slice(0, limit).map((b) => (
            <Tile
              key={b.properties.id}
              bench={b.properties}
              selected={b.properties.id === selectedId}
              onSelect={onSelect}
              onOpen={onOpen}
            />
          ))}
        </div>
        {hasMore ? (
          <div ref={sentinel} className="gridsentinel" aria-hidden="true" />
        ) : null}
        {hasMore ? (
          <button
            type="button"
            className="more gridmore"
            onClick={() => setLimit((l) => l + ALL_MAX)}
          >
            Show more
          </button>
        ) : null}
      </section>
    )
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
            {countLabel ?? `${benches.toLocaleString("en")} in view`}
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
            onOpen={onOpen}
          />
        ))}
      </div>
    </section>
  )
}
