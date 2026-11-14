import { type FormEvent, type ReactNode, useState } from "react"
import { Link } from "react-router-dom"
import { useMe } from "../data/social"
import { useAuth } from "../lib/auth"
import { SearchIcon, UserIcon } from "./Icons"

interface TopBarProps {
  /** When set, shows the place search and calls back with the query. */
  onSearch?: (query: string) => void
  children?: ReactNode
}

export function TopBar({ onSearch }: TopBarProps) {
  const [query, setQuery] = useState("")
  const { user, openSignIn } = useAuth()
  const { data: me } = useMe()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (q) onSearch?.(q)
  }

  return (
    <header className="bar">
      <Link className="wordmark" to="/">
        <b className="caps">Bench Finder</b>
        <span className="serial">Amsterdam</span>
      </Link>
      {onSearch ? (
        // biome-ignore lint/a11y/useSemanticElements: <search> is not in the React 19 JSX types yet
        <form className="search" role="search" onSubmit={submit}>
          <label htmlFor="place-search" className="searchicon">
            <SearchIcon />
            <span className="sr">Search</span>
          </label>
          <input
            id="place-search"
            type="search"
            placeholder="Search a place"
            autoComplete="off"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </form>
      ) : null}
      <span className="spacer" />
      {me?.isAdmin ? (
        <Link className="textbtn" to="/admin">
          <span>Moderate</span>
        </Link>
      ) : null}
      {user ? (
        <Link className="textbtn" to="/me">
          <UserIcon />
          <span className="signin-label">
            {user.name?.split(" ")[0] ?? "You"}
          </span>
        </Link>
      ) : (
        <button type="button" className="textbtn" onClick={openSignIn}>
          <UserIcon />
          <span className="signin-label">Sign in</span>
        </button>
      )}
    </header>
  )
}
