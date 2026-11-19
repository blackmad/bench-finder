import { useState } from "react"
import { MissingBenchDialog } from "./account/ReportDialogs"

export const REPO_URL = "https://github.com/blackmad/bench-finder"
export const DATA_URL = `${REPO_URL}/tree/main/export`

/**
 * The foot of the rail and the bench page: report a bench the map is missing
 * (pin starts at `center`), and where the data and code live.
 */
export function SiteFooter({
  center,
  missing = true,
}: {
  center: { lat: number; lng: number }
  /** Off where a report row nearby already offers it. */
  missing?: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <footer className="sitefoot">
      {missing ? (
        <p>
          Know a bench that is not on the map?{" "}
          <button
            type="button"
            className="linkbtn"
            onClick={() => setOpen(true)}
          >
            Report a missing bench
          </button>
        </p>
      ) : null}
      <p className="small">
        <a href={DATA_URL} target="_blank" rel="noreferrer">
          Download the data (CSV)
        </a>
        {" · "}
        <a href={REPO_URL} target="_blank" rel="noreferrer">
          Code on GitHub
        </a>
        {" · "}Bench locations © OpenStreetMap contributors
      </p>
      {open ? (
        <MissingBenchDialog center={center} onClose={() => setOpen(false)} />
      ) : null}
    </footer>
  )
}
