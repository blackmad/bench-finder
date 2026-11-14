// axe-core audit of every route, with the sign-in and report dialogs open too.
// Needs a running dev server and puppeteer-core with a local Chrome:
//   npm run fixture && npx vite --port 5194 --strictPort
//   npm i --no-save puppeteer-core && node scripts/axe.mjs [http://localhost:5194]
// CHROME=/path/to/chrome overrides the default macOS location. Exits 1 on any
// violation. Social/admin calls error without a Worker; that state is audited.
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import puppeteer from "puppeteer-core"

const AXE = readFileSync(
  createRequire(import.meta.url).resolve("axe-core/axe.min.js"),
  "utf8"
)
const base = process.argv[2] ?? "http://localhost:5194"
const routes = [
  ["/", null],
  ["/bench/394", null],
  ["/me", null],
  ["/admin", null],
  ["/no-such-page", null],
  ["/", "header button:last-of-type"],
  ["/bench/394", "report"],
]
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await puppeteer.launch({
  executablePath:
    process.env.CHROME ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
})
let total = 0
for (const width of [1440, 390]) {
  for (const [path, open] of routes) {
    const page = await browser.newPage()
    const phone = width < 600
    await page.setViewport({
      width,
      height: phone ? 844 : 900,
      isMobile: phone,
      hasTouch: phone,
    })
    await page.goto(base + path, { waitUntil: "networkidle0", timeout: 60000 })
    await sleep(1500)
    if (open === "report") {
      await page.evaluate(() =>
        [...document.querySelectorAll("button")]
          .find((b) => /report this/i.test(b.textContent ?? ""))
          ?.click()
      )
    } else if (open) {
      await page.click(open)
    }
    if (open) await sleep(1000)
    await page.evaluate(AXE)
    const violations = await page.evaluate(async () => {
      const r = await window.axe.run(document)
      return r.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target.join(" ")),
      }))
    })
    total += violations.length
    console.log(
      `${width} ${path}${open ? " (dialog)" : ""}: ${violations.length} violations`
    )
    for (const v of violations) {
      console.log(`  ${v.id}: ${v.nodes.slice(0, 4).join(", ")}`)
    }
    await page.close()
  }
}
await browser.close()
process.exit(total ? 1 : 0)
