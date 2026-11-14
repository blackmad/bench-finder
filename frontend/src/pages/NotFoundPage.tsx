import { Link } from "react-router-dom"
import { TopBar } from "../components/TopBar"

export default function NotFoundPage() {
  return (
    <>
      <TopBar />
      <main className="mx-auto max-w-[1240px] px-4 py-16 md:px-8">
        <p className="serial">404</p>
        <h1 className="mb-3 text-[clamp(30px,3.1vw,42px)] leading-[1.02] font-[750] tracking-[-0.015em] [font-variation-settings:'wdth'_112]">
          No bench at this address
        </h1>
        <p className="mb-6 max-w-[34ch] text-[16.5px] text-ink-2">
          The page you asked for is not on the map.
        </p>
        <Link className="textbtn" to="/">
          Back to the map
        </Link>
      </main>
    </>
  )
}
