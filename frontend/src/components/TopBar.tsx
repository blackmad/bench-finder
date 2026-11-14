import { type FormEvent, type ReactNode, useState } from "react"
import { Link } from "react-router-dom"
import { SearchIcon, UserIcon } from "./Icons"

interface TopBarProps {
  /** When set, shows the place search and calls back with the query. */
  onSearch?: (query: string) => void
  children?: ReactNode
}

export function TopBar({ onSearch }: TopBarProps) {
  const [query, setQuery] = useState("")

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
      <Link className="textbtn" to="/me">
        <UserIcon />
        <span className="signin-label">Sign in</span>
      </Link>
    </header>
  )
}
