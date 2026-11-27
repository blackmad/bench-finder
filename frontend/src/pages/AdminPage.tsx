import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Link } from "react-router-dom"
import { Photo } from "../components/Photo"
import { TopBar } from "../components/TopBar"
import {
  useDismissView,
  useHeroSuggestions,
  useResolveSuggestion,
  useViewSuggestions,
} from "../data/heroes"
import { useBenchIndex } from "../data/hooks"
import {
  type BenchPhoto,
  useModeratePhoto,
  usePendingPhotos,
  usePhotoSrc,
} from "../data/photos"
import { useMe } from "../data/social"
import { adminPhotoUrl, api, unwrap } from "../lib/api"
import { useAuth } from "../lib/auth"

const H1 =
  "mb-3 text-[clamp(30px,3.1vw,42px)] leading-[1.02] font-[750] tracking-[-0.015em] [font-variation-settings:'wdth'_112]"

interface BenchReport {
  id: number
  bench_id: number
  reason: string
  note: string | null
  photo_key: string | null
  user_id: string | null
  created_at: string
}
interface MissingReport {
  id: number
  lat: number
  lng: number
  pano_source: "amsterdam" | "google" | null
  pano_id: string | null
  pano_heading: number | null
  pano_url: string | null
  note: string | null
  photo_key: string | null
  user_id: string | null
  created_at: string
}
interface FlaggedComment {
  id: number
  bench_id: number
  display_name: string
  body: string
  created_at: string
}

const REASON_LABEL: Record<string, string> = {
  not_a_bench: "No bench here",
  wrong_location: "Wrong location",
  wrong_facing: "Wrong facing",
  bad_image: "Bad image",
  other: "Other",
}

export default function AdminPage() {
  const { user, ready, openSignIn } = useAuth()
  const { data: me, isPending } = useMe()

  let body: React.ReactNode
  if (!ready) body = null
  else if (!user)
    body = (
      <div className="stack">
        <p className="max-w-[44ch] text-[16.5px] text-ink-2">
          Moderators sign in to review reports and flagged notes.
        </p>
        <div>
          <button type="button" className="btn primary" onClick={openSignIn}>
            Sign in
          </button>
        </div>
      </div>
    )
  else if (isPending) body = <p className="state">Checking access...</p>
  else if (!me?.isAdmin)
    body = (
      <p className="max-w-[44ch] text-[16.5px] text-ink-2">
        This page is for moderators. <Link to="/">Back to the map</Link>
      </p>
    )
  else body = <Queue />

  return (
    <>
      <TopBar />
      <main className="mx-auto max-w-[1240px] px-4 py-10 md:px-8">
        <h1 className={H1}>Moderation</h1>
        {body}
      </main>
    </>
  )
}

function Queue() {
  const reports = useQuery({
    queryKey: ["admin", "reports"],
    queryFn: async () =>
      unwrap<{ bench: BenchReport[]; missing: MissingReport[] }>(
        await api.api.admin.reports.$get({ query: { status: "pending" } })
      ),
  })
  const comments = useQuery({
    queryKey: ["admin", "comments"],
    queryFn: async () =>
      unwrap<{ comments: FlaggedComment[] }>(
        await api.api.admin.comments.$get({ query: { state: "flagged" } })
      ),
  })
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin"] })

  const reportAction = useMutation({
    mutationFn: async (v: {
      kind: "bench" | "missing"
      id: number
      action: "resolve" | "dismiss"
    }) =>
      unwrap(
        await api.api.admin.reports[":kind"][":id"][":action"].$post({
          param: { kind: v.kind, id: String(v.id), action: v.action },
        })
      ),
    onSuccess: refresh,
  })
  const commentAction = useMutation({
    mutationFn: async (v: { id: number; action: "hide" | "approve" }) =>
      unwrap(
        await api.api.admin.comments[":id"][":action"].$post({
          param: { id: String(v.id), action: v.action },
        })
      ),
    onSuccess: refresh,
  })

  const err =
    reports.error ?? comments.error ?? reportAction.error ?? commentAction.error
  return (
    <div className="queue">
      {err ? (
        <p role="alert" className="form-error">
          {err.message}
        </p>
      ) : null}

      <section className="block" aria-labelledby="q-bench">
        <div className="blockhead">
          <h2 id="q-bench">Bench reports</h2>
          <p>{reports.data?.bench.length ?? 0} pending</p>
        </div>
        <ul className="qlist">
          {reports.data?.bench.length === 0 ? (
            <li className="hint">Nothing waiting.</li>
          ) : null}
          {reports.data?.bench.map((r) => (
            <li key={r.id} className="qitem">
              <div>
                <p className="qtitle">
                  <Link to={`/?bench=${r.bench_id}`}>
                    Bench No. {r.bench_id}
                  </Link>
                  <span className="tagpill">
                    {REASON_LABEL[r.reason] ?? r.reason}
                  </span>
                </p>
                {r.note ? <p className="cbody">{r.note}</p> : null}
                <p className="cmeta">
                  {r.user_id ? "Signed-in user" : "Anonymous"} ·{" "}
                  {new Date(r.created_at).toLocaleString()}
                </p>
                {r.photo_key ? <AdminPhoto photoKey={r.photo_key} /> : null}
              </div>
              <div className="row">
                <button
                  type="button"
                  className="btn"
                  onClick={() =>
                    reportAction.mutate({
                      kind: "bench",
                      id: r.id,
                      action: "resolve",
                    })
                  }
                >
                  Resolve
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() =>
                    reportAction.mutate({
                      kind: "bench",
                      id: r.id,
                      action: "dismiss",
                    })
                  }
                >
                  Dismiss
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="block" aria-labelledby="q-missing">
        <div className="blockhead">
          <h2 id="q-missing">Missing benches</h2>
          <p>{reports.data?.missing.length ?? 0} pending</p>
        </div>
        <ul className="qlist">
          {reports.data?.missing.length === 0 ? (
            <li className="hint">Nothing waiting.</li>
          ) : null}
          {reports.data?.missing.map((r) => (
            <li key={r.id} className="qitem">
              <div>
                <p className="qtitle">
                  <a
                    href={`https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lng}#map=19/${r.lat}/${r.lng}`}
                    rel="noreferrer"
                    className="num"
                  >
                    {r.lat.toFixed(5)}, {r.lng.toFixed(5)}
                  </a>
                </p>
                {r.note ? <p className="cbody">{r.note}</p> : null}
                {r.pano_id ? (
                  <p className="cmeta">
                    <a
                      href={
                        r.pano_url ??
                        `https://api.data.amsterdam.nl/panorama/panoramas/${r.pano_id}/`
                      }
                      target="_blank"
                      rel="noreferrer"
                    >
                      {r.pano_source === "google"
                        ? "Street View"
                        : "City panorama"}
                    </a>
                    , bench at {Math.round(r.pano_heading ?? 0)}°
                  </p>
                ) : null}
                <p className="cmeta">
                  {r.user_id ? "Signed-in user" : "Anonymous"} ·{" "}
                  {new Date(r.created_at).toLocaleString()}
                </p>
                {r.photo_key ? <AdminPhoto photoKey={r.photo_key} /> : null}
              </div>
              <div className="row">
                <button
                  type="button"
                  className="btn"
                  onClick={() =>
                    reportAction.mutate({
                      kind: "missing",
                      id: r.id,
                      action: "resolve",
                    })
                  }
                >
                  Resolve
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() =>
                    reportAction.mutate({
                      kind: "missing",
                      id: r.id,
                      action: "dismiss",
                    })
                  }
                >
                  Dismiss
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="block" aria-labelledby="q-comments">
        <div className="blockhead">
          <h2 id="q-comments">Flagged notes</h2>
          <p>{comments.data?.comments.length ?? 0} flagged</p>
        </div>
        <ul className="qlist">
          {comments.data?.comments.length === 0 ? (
            <li className="hint">Nothing flagged.</li>
          ) : null}
          {comments.data?.comments.map((c) => (
            <li key={c.id} className="qitem">
              <div>
                <p className="cbody">{c.body}</p>
                <p className="cmeta">
                  {c.display_name} on{" "}
                  <Link to={`/?bench=${c.bench_id}`}>
                    bench No. {c.bench_id}
                  </Link>
                </p>
              </div>
              <div className="row">
                <button
                  type="button"
                  className="btn"
                  onClick={() =>
                    commentAction.mutate({ id: c.id, action: "approve" })
                  }
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() =>
                    commentAction.mutate({ id: c.id, action: "hide" })
                  }
                >
                  Hide
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <PendingPhotos />
      <HeroSuggestions />
      <ViewSuggestions />
    </div>
  )
}

/** Visitors' lead photo suggestions: the current lead beside the suggested one. */
function PendingPhotos() {
  const { data, error } = usePendingPhotos(true)
  const moderate = useModeratePhoto()
  const byId = useBenchIndex()
  const list = data?.photos ?? []
  return (
    <section className="block" aria-labelledby="q-photos">
      <div className="blockhead">
        <h2 id="q-photos">Visitors' photos</h2>
        <p>{list.length} to check</p>
      </div>
      {error || moderate.error ? (
        <p role="alert" className="form-error">
          {(error ?? moderate.error)?.message}
        </p>
      ) : null}
      <ul className="qlist">
        {data && list.length === 0 ? (
          <li className="hint">No photos waiting.</li>
        ) : null}
        {list.map((p) => (
          <li key={p.id} className="qitem">
            <div>
              <PendingPhoto photo={p} />
              <p className="cmeta">
                {p.who} on{" "}
                <Link to={`/?bench=${p.benchId}`}>
                  {byId.get(p.benchId ?? 0)?.properties.address ?? "bench"} No.{" "}
                  {p.benchId}
                </Link>
              </p>
            </div>
            <div className="row">
              <button
                type="button"
                className="btn"
                disabled={moderate.isPending}
                onClick={() => moderate.mutate({ id: p.id, action: "approve" })}
              >
                Show it
              </button>
              <button
                type="button"
                className="btn"
                disabled={moderate.isPending}
                onClick={() => moderate.mutate({ id: p.id, action: "hide" })}
              >
                Hide
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function PendingPhoto({ photo }: { photo: BenchPhoto }) {
  const src = usePhotoSrc(photo)
  return src ? (
    <a href={src} target="_blank" rel="noreferrer" className="qphoto">
      <img src={src} alt={`Shared by ${photo.who}`} width={320} height={240} />
    </a>
  ) : null
}

function HeroSuggestions() {
  const { data, error } = useHeroSuggestions()
  const resolve = useResolveSuggestion()
  const byId = useBenchIndex()
  const list = data?.suggestions ?? []
  return (
    <section className="block" aria-labelledby="q-heroes">
      <div className="blockhead">
        <h2 id="q-heroes">Lead photo suggestions</h2>
        <p>{list.length} open</p>
      </div>
      {error || resolve.error ? (
        <p role="alert" className="form-error">
          {(error ?? resolve.error)?.message}
        </p>
      ) : null}
      <ul className="qlist">
        {data && list.length === 0 ? (
          <li className="hint">No suggestions.</li>
        ) : null}
        {list.map((s) => {
          const f = byId.get(s.benchId)?.properties
          const now = s.current?.urls ?? f?.hero_urls
          return (
            <li key={s.id} className="qitem">
              <div>
                <div className="qheroes">
                  <figure>
                    {now ? (
                      <Photo
                        urls={now}
                        sizes="220px"
                        alt="Current lead photo"
                        width={220}
                        height={220}
                        loading="lazy"
                      />
                    ) : (
                      <span className="hint">No lead photo</span>
                    )}
                    <figcaption>Now</figcaption>
                  </figure>
                  <figure>
                    <Photo
                      urls={s.photo.urls}
                      webp={s.photo.urls_webp}
                      sizes="220px"
                      alt="Suggested lead photo"
                      width={220}
                      height={220}
                      loading="lazy"
                    />
                    <figcaption>Suggested</figcaption>
                  </figure>
                </div>
                <p className="cmeta">
                  {s.who} on{" "}
                  <Link to={`/?bench=${s.benchId}`}>
                    {f?.address ?? "bench"} No. {s.benchId}
                  </Link>
                </p>
              </div>
              <div className="row">
                <button
                  type="button"
                  className="btn"
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate({ id: s.id, action: "accept" })}
                >
                  Use it
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={resolve.isPending}
                  onClick={() =>
                    resolve.mutate({ id: s.id, action: "dismiss" })
                  }
                >
                  Dismiss
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** Street View cameras people framed; `bench_finder.view_suggestions` renders them. */
function ViewSuggestions() {
  const { data, error } = useViewSuggestions()
  const dismiss = useDismissView()
  const views = data?.views ?? []
  const open = views.filter((v) => v.state === "pending").length
  return (
    <section className="block" aria-labelledby="q-views">
      <div className="blockhead">
        <h2 id="q-views">Suggested Street View cameras</h2>
        <p>{open} to render</p>
      </div>
      <p className="hint">
        Render pending ones with{" "}
        <code>python -m bench_finder.view_suggestions</code>; after the next
        publish they appear in the bench's photos, where you can make one the
        lead.
      </p>
      {error || dismiss.error ? (
        <p role="alert" className="form-error">
          {(error ?? dismiss.error)?.message}
        </p>
      ) : null}
      <ul className="qlist">
        {data && views.length === 0 ? (
          <li className="hint">No suggested views.</li>
        ) : null}
        {views.map((v) => (
          <li key={v.id} className="qitem">
            <div>
              <p>
                <b>
                  {v.state === "pending"
                    ? "To render"
                    : v.state === "rendered"
                      ? "Rendered"
                      : "Failed"}
                </b>{" "}
                · looking {Math.round(v.heading)}°, {Math.round(v.fov)}° wide
                {v.error ? ` · ${v.error}` : ""}
              </p>
              <p className="cmeta">
                {v.who} on{" "}
                <Link to={`/?bench=${v.benchId}`}>bench No. {v.benchId}</Link> ·{" "}
                <a
                  href={`https://www.google.com/maps/@?api=1&map_action=pano&pano=${encodeURIComponent(v.panoId)}&heading=${Math.round(v.heading)}&pitch=${Math.round(v.pitch)}&fov=${Math.round(v.fov)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in Street View
                </a>
              </p>
            </div>
            <div className="row">
              <button
                type="button"
                className="btn"
                disabled={dismiss.isPending}
                onClick={() => dismiss.mutate(v.id)}
              >
                Dismiss
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function AdminPhoto({ photoKey }: { photoKey: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  if (url)
    return <img className="qphoto" src={url} alt="Attached to the report" />
  return (
    <button
      type="button"
      className="linkbtn"
      onClick={() =>
        adminPhotoUrl(photoKey).then(setUrl, () => setFailed(true))
      }
    >
      {failed ? "Photo unavailable" : "Show photo"}
    </button>
  )
}
