import { useState } from "react"
import { useClearHero, useSetHero, useSuggestHero } from "../../data/heroes"
import { useMe } from "../../data/social"
import type { GalleryImage } from "../../data/types"
import { useAuth } from "../../lib/auth"

/** Under a gallery photo: moderators make it the lead; anyone else suggests it. */
export function HeroButton({
  benchId,
  image,
}: {
  benchId: number
  image: GalleryImage
}) {
  const { user, openSignIn } = useAuth()
  const { data: me } = useMe()
  const set = useSetHero(benchId)
  const suggest = useSuggestHero(benchId)
  const [done, setDone] = useState(false)
  const id = image.id
  // Photos from publishes before image ids were added cannot be named.
  if (id === undefined) return null
  const g = { ...image, id }
  const m = me?.isAdmin ? set : suggest
  if (done && !me?.isAdmin)
    return <p className="heroact done">Suggested, thank you</p>
  return (
    <p className="heroact">
      <button
        type="button"
        className="linkbtn"
        disabled={m.isPending}
        onClick={() =>
          user ? m.mutate(g, { onSuccess: () => setDone(true) }) : openSignIn()
        }
      >
        {me?.isAdmin ? "Use as lead photo" : "Suggest as lead photo"}
      </button>
      {m.error ? (
        <span role="alert" className="form-error">
          {" "}
          {m.error.message}
        </span>
      ) : null}
    </p>
  )
}

/** Moderators: a lead photo picked on the site can go back to the automatic one. */
export function ClearHero({ benchId }: { benchId: number }) {
  const { data: me } = useMe()
  const clear = useClearHero(benchId)
  if (!me?.isAdmin) return null
  return (
    <button
      type="button"
      className="linkbtn heroclear"
      disabled={clear.isPending}
      onClick={() => clear.mutate()}
    >
      Back to the automatic lead photo
    </button>
  )
}
