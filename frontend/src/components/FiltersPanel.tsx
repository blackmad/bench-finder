import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react"
import {
  activeCount,
  type Coverage,
  FACES,
  type Filters,
  MATERIALS,
  MIN_FIELD,
  NO_FILTERS,
  type Offered,
  type OptionCounts,
  SEAT_BUCKETS,
  SECTOR_LONG,
  SECTORS,
  type Tri,
  TYPES,
  toggled,
} from "../data/filters"
import type { FacesCategory } from "../data/types"
import { CheckTick, SlidersIcon } from "./Icons"

const PHONE = "(max-width: 760px)"

const MATERIAL_LABEL: Record<(typeof MATERIALS)[number], string> = {
  wood: "Wood",
  metal: "Metal",
  stone: "Stone",
  concrete: "Concrete",
  plastic: "Plastic",
  other: "Other",
}
const SEAT_LABEL: Record<(typeof SEAT_BUCKETS)[number], string> = {
  "1-2": "1–2",
  "3": "3",
  "4": "4",
  "5+": "5 or more",
}
const FACES_LABEL: Record<FacesCategory, string> = {
  water: "Water",
  park: "Park",
  square: "Square",
  street: "Street",
  playground: "Playground",
  wall: "A wall",
  other: "Something else",
}
const TYPE_LABEL: Record<(typeof TYPES)[number], string> = {
  backrest: "Bench with backrest",
  backless: "Backless bench",
  picnic: "Picnic table",
  other: "Other seat",
}

const fmt = (n: number) => n.toLocaleString("en")

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
  coverage: Coverage
  offered: Offered
  counts: OptionCounts
  /** Benches matching the filters, everywhere and in the map view. */
  matching: number
  matchingInView: number
}

/**
 * The Filters button on the map and the panel it opens: a popover beside the
 * map on desktop (non-modal, so the map stays live), a bottom sheet on phones
 * (modal). Changes apply at once; the URL carries them.
 */
export function FiltersPanel(props: Props) {
  const { filters, onChange, matching, matchingInView } = props
  const [open, setOpen] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const titleId = useId()
  const n = activeCount(filters)

  useEffect(() => {
    const d = dialogRef.current
    if (!d) return
    if (open && !d.open) {
      if (window.matchMedia(PHONE).matches) d.showModal()
      else d.show()
      d.querySelector<HTMLElement>(".fclose")?.focus()
    } else if (!open && d.open) {
      d.close()
    }
  }, [open])

  const close = useCallback(() => {
    setOpen(false)
    buttonRef.current?.focus()
  }, [])

  const onKeyDown = (e: KeyboardEvent<HTMLDialogElement>) => {
    // A non-modal dialog does not close on Esc by itself.
    if (e.key === "Escape") {
      e.preventDefault()
      close()
    }
  }

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="filterbtn"
        aria-expanded={open}
        aria-controls="filters"
        onClick={() => (open ? close() : setOpen(true))}
      >
        <SlidersIcon />
        Filters
        {n ? (
          <span className="badge num">
            {n}
            <span className="sr"> active</span>
          </span>
        ) : null}
      </button>
      <dialog
        ref={dialogRef}
        id="filters"
        className="filters"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
        onClose={() => setOpen(false)}
      >
        <div className="fhead">
          <h2 id={titleId} className="caps">
            Filters
          </h2>
          <button
            type="button"
            className="fclose"
            aria-label="Close filters"
            onClick={close}
          >
            <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </div>
        {open ? <FilterControls {...props} /> : null}
        <div className="ffoot">
          <p className="fcount" role="status" aria-live="polite">
            <b className="num">{fmt(matching)}</b>{" "}
            {matching === 1 ? "bench matches" : "benches match"}
            <small className="num">{fmt(matchingInView)} in view</small>
          </p>
          <button
            type="button"
            className="textbtn"
            disabled={!n}
            onClick={() => onChange(NO_FILTERS)}
          >
            Clear
          </button>
          <button type="button" className="btn solid" onClick={close}>
            {matching ? `Show ${fmt(matchingInView)}` : "Done"}
          </button>
        </div>
      </dialog>
    </>
  )
}

function FilterControls({
  filters: f,
  onChange,
  coverage: c,
  offered: o,
  counts,
}: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch })
  const missing = [
    !o.materials && "material",
    !o.lit && "lighting",
    !o.seats && "seat count",
    !o.faces && "what it looks at",
    !o.types && "kind of seat",
    !o.backrest && "backrest",
  ].filter((x): x is string => Boolean(x))

  return (
    <div className="fbody">
      <fieldset className="fgroup facinggroup">
        <legend className="caps">Facing</legend>
        {o.facing ? (
          <>
            <CompassPicker
              selected={f.dirs}
              counts={counts.dirs}
              onToggle={(i) => set({ dirs: toggled(f.dirs, i) })}
            />
            <p className="fhint">
              {f.dirs.size
                ? `Facing ${[...f.dirs]
                    .sort((a, b) => a - b)
                    .map((i) => SECTORS[i])
                    .join(" or ")}`
                : "Any direction. Pick one or more."}
              {f.dirs.size ? (
                <button
                  type="button"
                  className="linkbtn"
                  onClick={() => set({ dirs: new Set() })}
                >
                  Any direction
                </button>
              ) : null}
            </p>
            {o.facingSplit ? (
              <Choice
                label="How the facing is known"
                value={f.facing}
                onChange={(v) => set({ facing: v })}
                options={[
                  ["known", "Known", counts.facing.known],
                  ["mapped", "Mapped", counts.facing.mapped],
                  ["estimated", "≈ Estimated", counts.facing.estimated],
                ]}
              />
            ) : (
              <Check
                checked={f.facing !== null}
                onChange={(on) => set({ facing: on ? "known" : null })}
                count={counts.facing.known}
              >
                Facing known
              </Check>
            )}
            <p className="fnote">
              {fmt(c.facing)} of {fmt(c.total)} benches have a facing
              {c.estimated ? "; ≈ marks an estimate from street views" : ""}.
            </p>
          </>
        ) : (
          <p className="fnote">Not mapped yet.</p>
        )}
      </fieldset>

      {o.photo ? (
        <div className="fgroup">
          <Check
            checked={f.photo}
            onChange={(on) => set({ photo: on })}
            count={counts.photo}
          >
            Has a photo
          </Check>
        </div>
      ) : null}

      {o.backrest ? (
        <Choice
          label="Backrest"
          value={f.backrest}
          onChange={(v) => set({ backrest: v })}
          options={triOptions(counts.backrest, "With", "Without")}
        />
      ) : null}

      {o.lit ? (
        <Choice
          label="Lit at night"
          value={f.lit}
          onChange={(v) => set({ lit: v })}
          options={triOptions(counts.lit, "Lit", "Not lit")}
        />
      ) : null}

      {o.materials ? (
        <Checks
          label="Material"
          all={MATERIALS}
          labels={MATERIAL_LABEL}
          counts={counts.materials}
          selected={f.materials}
          onChange={(s) => set({ materials: s })}
        />
      ) : null}

      {o.seats ? (
        <Checks
          label="Seats"
          all={SEAT_BUCKETS}
          labels={SEAT_LABEL}
          counts={counts.seats}
          selected={f.seats}
          onChange={(s) => set({ seats: s })}
        />
      ) : null}

      {o.faces ? (
        <Checks
          label="Looks at"
          all={FACES}
          labels={FACES_LABEL}
          counts={counts.faces}
          selected={f.faces}
          onChange={(s) => set({ faces: s })}
        />
      ) : null}

      {o.types ? (
        <Checks
          label="Kind of seat"
          all={TYPES}
          labels={TYPE_LABEL}
          counts={counts.types}
          selected={f.types}
          onChange={(s) => set({ types: s })}
        />
      ) : null}

      {missing.length ? (
        <p className="fnote fmissing">
          <b>Not mapped yet:</b> {missing.join(", ")}. These filters appear once
          at least {MIN_FIELD} benches have the data.
        </p>
      ) : null}
    </div>
  )
}

const triOptions = (
  n: Record<Tri, number>,
  yes: string,
  no: string
): [Tri, string, number][] => [
  ["yes", yes, n.yes],
  ["no", no, n.no],
]

/** A row of square radio cells with "Any" first. Arrow keys move natively. */
function Choice<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: T | null
  onChange: (v: T | null) => void
  options: [T, string, number][]
}) {
  const name = useId()
  const all: [T | null, string, number | null][] = [
    [null, "Any", null],
    ...options,
  ]
  return (
    <fieldset className="fgroup">
      <legend className="caps">{label}</legend>
      <div className="seg">
        {all.map(([v, text, count]) => (
          <label key={v ?? "any"}>
            <input
              type="radio"
              name={name}
              checked={value === v}
              onChange={() => onChange(v)}
            />
            <span>
              {text}
              {count !== null ? (
                <small className="num">{fmt(count)}</small>
              ) : null}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Check({
  checked,
  onChange,
  count,
  children,
}: {
  checked: boolean
  onChange: (on: boolean) => void
  count: number
  children: string
}) {
  return (
    <label className="check fcheck">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="box">
        <CheckTick />
      </span>
      {children}
      <small className="num">{fmt(count)}</small>
    </label>
  )
}

/** Multi-choice group; options no bench has are left out. */
function Checks<T extends string>({
  label,
  all,
  labels,
  counts,
  selected,
  onChange,
}: {
  label: string
  all: readonly T[]
  labels: Record<T, string>
  counts: Record<T, number>
  selected: ReadonlySet<T>
  onChange: (s: Set<T>) => void
}) {
  const shown = all.filter((v) => counts[v] > 0 || selected.has(v))
  return (
    <fieldset className="fgroup">
      <legend className="caps">{label}</legend>
      <div className="fchecks">
        {shown.map((v) => (
          <Check
            key={v}
            checked={selected.has(v)}
            onChange={() => onChange(toggled(selected, v))}
            count={counts[v]}
          >
            {labels[v]}
          </Check>
        ))}
      </div>
    </fieldset>
  )
}

/* The compass picker: the signature datum as a control. */

const R_IN = 15
const R_OUT = 44
const polar = (deg: number, r: number) => {
  const a = (deg * Math.PI) / 180
  return [Math.sin(a) * r, -Math.cos(a) * r] as const
}
const wedge = (i: number) => {
  const a0 = i * 45 - 22.5
  const a1 = i * 45 + 22.5
  const [x0, y0] = polar(a0, R_OUT)
  const [x1, y1] = polar(a1, R_OUT)
  const [x2, y2] = polar(a1, R_IN)
  const [x3, y3] = polar(a0, R_IN)
  return `M${x0} ${y0}A${R_OUT} ${R_OUT} 0 0 1 ${x1} ${y1}L${x2} ${y2}A${R_IN} ${R_IN} 0 0 0 ${x3} ${y3}Z`
}
const TICKS16 = Array.from({ length: 16 }, (_, i) => {
  const l = i % 2 ? 2 : 3.5
  const [x1, y1] = polar(i * 22.5 + 11.25, R_OUT)
  const [x2, y2] = polar(i * 22.5 + 11.25, R_OUT - l)
  return { x1, y1, x2, y2, key: i }
})
// Label buttons sit just outside the ring; the SVG spans -60..60.
const LABEL_R = 52.5
const VIEW = 120

/**
 * Eight toggle buttons around a postmark compass. Each wedge carries a petal
 * as long as the number of benches facing that way (sqrt-scaled), so the dial
 * shows where the data is before anything is picked. Arrow keys move around
 * the dial (one tab stop); Space or Enter toggles.
 */
function CompassPicker({
  selected,
  counts,
  onToggle,
}: {
  selected: ReadonlySet<number>
  counts: number[]
  onToggle: (i: number) => void
}) {
  const [focus, setFocus] = useState(0)
  const [hover, setHover] = useState<number | null>(null)
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const max = Math.max(1, ...counts)
  const petals = useMemo(
    () =>
      counts.map((n, i) => {
        if (!n) return null
        const len = 4 + (R_OUT - R_IN - 9) * Math.sqrt(n / max)
        const [x1, y1] = polar(i * 45, R_IN + 2.5)
        const [x2, y2] = polar(i * 45, R_IN + 2.5 + len)
        return { x1, y1, x2, y2 }
      }),
    [counts, max]
  )

  const move = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const step =
      e.key === "ArrowRight" || e.key === "ArrowDown"
        ? 1
        : e.key === "ArrowLeft" || e.key === "ArrowUp"
          ? -1
          : 0
    let next = i
    if (step) next = (i + step + 8) % 8
    else if (e.key === "Home") next = 0
    else if (e.key === "End") next = 7
    else return
    e.preventDefault()
    setFocus(next)
    refs.current[next]?.focus()
  }

  return (
    <div className="compass">
      <svg viewBox="-60 -60 120 120" aria-hidden="true">
        <circle r={R_OUT + 3} fill="var(--color-stamp-paper)" />
        {SECTORS.map((s, i) => (
          // biome-ignore lint/a11y/noStaticElementInteractions: pointer target only; the labelled button is the keyboard path
          <path
            key={s}
            d={wedge(i)}
            className={`wedge${selected.has(i) ? " on" : ""}${hover === i ? " hover" : ""}`}
            onClick={() => {
              setFocus(i)
              onToggle(i)
            }}
            onPointerEnter={() => setHover(i)}
            onPointerLeave={() => setHover(null)}
          />
        ))}
        <circle
          r={R_OUT}
          fill="none"
          stroke="var(--color-ink)"
          strokeWidth=".9"
        />
        <g stroke="var(--color-ink)" strokeWidth=".7">
          {TICKS16.map(({ key, ...t }) => (
            <line key={key} {...t} />
          ))}
        </g>
        <g strokeLinecap="round" strokeWidth="3.4">
          {petals.map((p, i) =>
            p ? (
              <line
                key={SECTORS[i]}
                {...p}
                stroke={
                  selected.has(i) ? "var(--color-airmail)" : "var(--color-ink)"
                }
              />
            ) : null
          )}
        </g>
        <circle
          r={R_IN}
          fill="var(--color-card)"
          stroke="var(--color-ink)"
          strokeWidth=".9"
        />
        <text
          y="4.6"
          textAnchor="middle"
          fontSize="12.5"
          fontWeight="800"
          fill="var(--color-ink)"
          fontFamily="Archivo Variable, sans-serif"
          style={{ fontVariationSettings: "'wdth' 112" }}
        >
          {fmt(
            counts.reduce(
              (a, n, i) => a + (!selected.size || selected.has(i) ? n : 0),
              0
            )
          )}
        </text>
      </svg>
      {SECTORS.map((s, i) => {
        const [x, y] = polar(i * 45, LABEL_R)
        const on = selected.has(i)
        return (
          <button
            key={s}
            ref={(el) => {
              refs.current[i] = el
            }}
            type="button"
            className="dir"
            style={{
              left: `${50 + (x / VIEW) * 100}%`,
              top: `${50 + (y / VIEW) * 100}%`,
            }}
            tabIndex={i === focus ? 0 : -1}
            aria-pressed={on}
            aria-label={`${s}, facing ${SECTOR_LONG[i]}, ${counts[i]} ${counts[i] === 1 ? "bench" : "benches"}`}
            onClick={() => {
              setFocus(i)
              onToggle(i)
            }}
            onKeyDown={(e) => move(e, i)}
            onFocus={() => setFocus(i)}
            onPointerEnter={() => setHover(i)}
            onPointerLeave={() => setHover(null)}
          >
            {s}
          </button>
        )
      })}
    </div>
  )
}
