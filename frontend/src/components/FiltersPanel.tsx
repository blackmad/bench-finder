import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useId,
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
  residential_street: "Quiet street",
  busy_street: "Busy street",
  courtyard: "Courtyard",
  playground: "Playground",
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

function FilterControls({ filters: f, onChange, offered: o, counts }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch })
  const missing = [
    !o.faces && "what it looks at",
    !o.materials && "material",
    !o.lit && "lighting",
    !o.seats && "seat count",
    !o.types && "kind of seat",
    !o.backrest && "backrest",
  ].filter((x): x is string => Boolean(x))

  return (
    <div className="fbody">
      {o.faces ? (
        <Checks
          label="Looks at"
          all={FACES}
          labels={FACES_LABEL}
          counts={counts.faces}
          selected={f.faces}
          onChange={(s) => set({ faces: s })}
          chips
        />
      ) : null}

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
  chips = false,
}: {
  label: string
  all: readonly T[]
  labels: Record<T, string>
  counts: Record<T, number>
  selected: ReadonlySet<T>
  onChange: (s: Set<T>) => void
  /** Toggle chips instead of a checkbox list (the lead "Looks at" group). */
  chips?: boolean
}) {
  const shown = all.filter((v) => counts[v] > 0 || selected.has(v))
  if (chips) {
    return (
      <fieldset className="fgroup">
        <legend className="caps">{label}</legend>
        <div className="fchips">
          {shown.map((v) => (
            <button
              key={v}
              type="button"
              className="chip"
              aria-pressed={selected.has(v)}
              onClick={() => onChange(toggled(selected, v))}
            >
              {labels[v]}
              <small className="num">{fmt(counts[v])}</small>
            </button>
          ))}
        </div>
      </fieldset>
    )
  }
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
