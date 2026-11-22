import { type FormEvent, useState } from "react"
import { Link } from "react-router-dom"
import { type Profile, pagePath, useUpdateProfile } from "../../data/social"
import { CheckTick } from "../Icons"

/** My benches: make the favourites a public page, its link, name and handle. */
export function PublicPageSettings({ profile }: { profile: Profile | null }) {
  const update = useUpdateProfile()
  const [handle, setHandle] = useState(profile?.handle ?? "")
  const [name, setName] = useState(profile?.displayName ?? "")
  const [copied, setCopied] = useState(false)
  const url = profile ? `${window.location.origin}${pagePath(profile)}` : null

  const save = (e: FormEvent) => {
    e.preventDefault()
    update.mutate({
      handle: handle.trim() ? handle.trim().toLowerCase() : null,
      ...(name.trim() ? { displayName: name.trim() } : {}),
    })
  }

  return (
    <section className="block pubpage" aria-labelledby="h-pub">
      <div className="blockhead">
        <h2 id="h-pub">Your public page</h2>
        <p>Share your favourite benches</p>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={profile?.public ?? false}
          disabled={update.isPending}
          onChange={(e) => update.mutate({ public: e.target.checked })}
        />
        <span className="box">
          <CheckTick />
        </span>
        <span>
          Make my favourites public. Anyone with the link sees them, in your
          order, with the name below. Your other lists stay private.
        </span>
      </label>
      {profile?.public && url ? (
        <p className="publink">
          <Link to={pagePath(profile)}>{url.replace(/^https?:\/\//, "")}</Link>
          <button
            type="button"
            className="linkbtn"
            onClick={() =>
              navigator.clipboard?.writeText(url).then(() => {
                setCopied(true)
                setTimeout(() => setCopied(false), 1500)
              })
            }
          >
            {copied ? "Copied" : "Copy link"}
          </button>
        </p>
      ) : null}
      {profile ? (
        <form className="pubform" onSubmit={save}>
          <label>
            <span className="caps">Name on the page</span>
            <input
              value={name}
              maxLength={40}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            <span className="caps">Handle (optional)</span>
            <span className="handle">
              /u/
              <input
                value={handle}
                maxLength={24}
                placeholder={profile.slug}
                onChange={(e) => setHandle(e.target.value)}
                autoCapitalize="none"
                spellCheck={false}
              />
            </span>
          </label>
          <button type="submit" className="btn" disabled={update.isPending}>
            Save
          </button>
        </form>
      ) : null}
      {update.error ? (
        <p role="alert" className="form-error">
          {update.error.message}
        </p>
      ) : null}
    </section>
  )
}
