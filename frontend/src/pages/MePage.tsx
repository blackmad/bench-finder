import { TopBar } from "../components/TopBar"

export default function MePage() {
  return (
    <>
      <TopBar />
      <main className="mx-auto max-w-[1240px] px-4 py-10 md:px-8">
        <h1 className="mb-3 text-[clamp(30px,3.1vw,42px)] leading-[1.02] font-[750] tracking-[-0.015em] [font-variation-settings:'wdth'_112]">
          Your benches
        </h1>
        <p className="max-w-[44ch] text-[16.5px] text-ink-2">
          Sign in to keep a list of the benches you have sat on and the ones you
          want to visit.
        </p>
      </main>
    </>
  )
}
