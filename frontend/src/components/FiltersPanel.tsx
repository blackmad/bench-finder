import type { FacesCategory } from "../data/types"
import { type Filters, toggled } from "../lib/filters"
import { CheckTick } from "./Icons"

const FACE_OPTS: [FacesCategory, string][] = [
  ["water", "Water"],
  ["park", "Park"],
  ["square", "Square"],
  ["street", "Street"],
]
const SECT = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

const point = (deg: number, r: number): [number, number] => [
  Math.sin((deg * Math.PI) / 180) * r,
  -Math.cos((deg * Math.PI) / 180) * r,
]

const sectorPath = (a0: number, a1: number, r0: number, r1: number) => {
  const [x0, y0] = point(a0, r1)
  const [x1, y1] = point(a1, r1)
  const [x2, y2] = point(a1, r0)
  const [x3, y3] = point(a0, r0)
  return `M${x0} ${y0}A${r1} ${r1} 0 0 1 ${x1} ${y1}L${x2} ${y2}A${r0} ${r0} 0 0 0 ${x3} ${y3}Z`
}

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
}

export function FiltersPanel({ filters, onChange }: Props) {
  const hint = filters.sectors.size
    ? `Facing ${[...filters.sectors]
        .sort((a, b) => a - b)
        .map((i) => SECT[i])
        .join(", ")}`
    : "Any direction"

  const toggleSector = (i: number) =>
    onChange({ ...filters, sectors: toggled(filters.sectors, i) })

  return (
    <section className="filters" id="filters" aria-label="Filters">
      <div>
        <div className="label caps">Looks at</div>
        <div className="checks">
          {FACE_OPTS.map(([v, label]) => (
            <label className="check" key={v}>
              <input
                type="checkbox"
                checked={filters.faces.has(v)}
                onChange={() =>
                  onChange({ ...filters, faces: toggled(filters.faces, v) })
                }
              />
              <span className="box">
                <CheckTick />
              </span>
              {label}
            </label>
          ))}
        </div>
        <div className="label caps" style={{ marginTop: 14 }}>
          Seat
        </div>
        <div className="checks">
          <label className="check">
            <input
              type="checkbox"
              checked={filters.backrest}
              onChange={(e) =>
                onChange({ ...filters, backrest: e.target.checked })
              }
            />
            <span className="box">
              <CheckTick />
            </span>
            Has a backrest
          </label>
        </div>
      </div>
      <div className="dialwrap">
        <div className="label caps">Facing</div>
        {/* biome-ignore lint/a11y/useSemanticElements: an SVG cannot be a fieldset */}
        <svg
          className="dial"
          viewBox="-50 -50 100 100"
          role="group"
          aria-label="Filter by facing direction"
        >
          {SECT.map((s, i) => {
            const a = i * 45
            const [lx, ly] = point(a, 33)
            const on = filters.sectors.has(i)
            return (
              <g key={s}>
                {/* biome-ignore lint/a11y/useSemanticElements: SVG sector cannot be a native button */}
                <path
                  className="sector"
                  tabIndex={0}
                  role="button"
                  aria-pressed={on}
                  aria-label={`Facing ${s}`}
                  d={sectorPath(a - 22.5, a + 22.5, 18, 47)}
                  onClick={() => toggleSector(i)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      toggleSector(i)
                    }
                  }}
                />
                <text className={`lab${on ? " on" : ""}`} x={lx} y={ly}>
                  {s}
                </text>
              </g>
            )
          })}
          <circle
            r="14"
            fill="var(--color-card)"
            stroke="var(--color-ink)"
            strokeWidth="1"
          />
          <path d="M0 -9 l-3.4 6 h6.8z" fill="var(--color-ink)" />
          <line
            x1="0"
            y1="-3"
            x2="0"
            y2="8"
            stroke="var(--color-ink)"
            strokeWidth="1.6"
          />
        </svg>
        <div className="dialhint">{hint}</div>
      </div>
      <p className="sheetnote">
        <span className="key">
          <span>
            <i /> Mapped facing
          </span>
          <span>
            <i className="est" /> Estimated (≈)
          </span>
        </span>
      </p>
    </section>
  )
}
