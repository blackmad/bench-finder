import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { useMe } from "../data/social"
import { useAuth } from "../lib/auth"
import { UserIcon } from "./Icons"
import { PlaceSearch } from "./PlaceSearch"

interface TopBarProps {
  /** When set, shows the place search and calls back with the chosen place. */
  onPlace?: (center: [number, number]) => void
  children?: ReactNode
}

export function TopBar({ onPlace }: TopBarProps) {
  const { user, openSignIn } = useAuth()
  const { data: me } = useMe()
  return (
    <header className="bar">
      <Link className="wordmark" to="/">
        <b className="caps">Bench Finder</b>
      </Link>
      {onPlace ? <PlaceSearch onPick={onPlace} /> : null}
      <span className="spacer" />
      {me?.isAdmin ? (
        <Link className="textbtn" to="/admin">
          <span>Moderate</span>
        </Link>
      ) : null}
      {user ? (
        <Link className="textbtn" to="/me" aria-label="Your benches">
          <UserIcon />
          <span className="signin-label">
            {user.name?.split(" ")[0] ?? "You"}
          </span>
        </Link>
      ) : (
        <button
          type="button"
          className="textbtn"
          onClick={openSignIn}
          aria-label="Sign in"
        >
          <UserIcon />
          <span className="signin-label">Sign in</span>
        </button>
      )}
    </header>
  )
}
