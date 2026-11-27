import { useRef } from "react"
import {
  type BenchPhoto,
  useBenchPhotos,
  useDeletePhoto,
  usePhotoSrc,
  useUploadPhoto,
} from "../../data/photos"
import { useAuth } from "../../lib/auth"

/** Visitors' own photos of the bench, and a button to add one. */
export function VisitorPhotos({ benchId }: { benchId: number }) {
  const { user, openSignIn } = useAuth()
  const { data } = useBenchPhotos(benchId)
  const upload = useUploadPhoto(benchId)
  const remove = useDeletePhoto(benchId)
  const input = useRef<HTMLInputElement>(null)
  const photos = data?.photos ?? []

  const add = () => (user ? input.current?.click() : openSignIn())

  return (
    <div className="pvviews pvphotos">
      <div className="rowhead">
        <h3 className="caps">Visitors' photos</h3>
        <button
          type="button"
          className="linkbtn"
          onClick={add}
          disabled={upload.isPending}
        >
          {upload.isPending ? "Uploading…" : "Add a photo"}
        </button>
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ""
            if (f) upload.mutate(f)
          }}
        />
      </div>
      {upload.error && upload.error.message !== "Choose a username to post" ? (
        <p role="alert" className="form-error">
          {upload.error.message}
        </p>
      ) : null}
      {upload.isSuccess ? (
        <p role="status" className="hint">
          Thanks! A moderator will check it before it shows to everyone.
        </p>
      ) : null}
      {photos.length ? (
        <div className="strip">
          {photos.map((p) => (
            <VisitorPhoto
              key={p.id}
              photo={p}
              onDelete={p.mine ? () => remove.mutate(p.id) : undefined}
            />
          ))}
        </div>
      ) : (
        <p className="hint">
          Sat here? Share a photo of the bench or its view.
        </p>
      )}
    </div>
  )
}

function VisitorPhoto({
  photo: p,
  onDelete,
}: {
  photo: BenchPhoto
  onDelete?: () => void
}) {
  const src = usePhotoSrc(p)
  return (
    <figure className="vphoto">
      {src ? (
        <a href={src} target="_blank" rel="noreferrer">
          <img
            src={src}
            alt={`Shared by ${p.who}`}
            width={p.width}
            height={p.height}
            loading="lazy"
          />
        </a>
      ) : (
        <div className="vphoto-empty" />
      )}
      <figcaption>
        <span>
          {p.who}
          {p.state === "pending" ? " · awaiting review" : ""}
        </span>
        {onDelete ? (
          <button type="button" className="linkbtn" onClick={onDelete}>
            Remove
          </button>
        ) : null}
      </figcaption>
    </figure>
  )
}
