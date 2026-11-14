// Renders public/og-image.png (1200x630) from og.html and the PNG app icons
// (apple-touch-icon 180, icon-192, icon-512) from icon.html, which is
// public/favicon.svg at size. Hand-drawn in HTML/SVG from the DESIGN.md tokens;
// no photos or generated imagery.
//
// puppeteer-core is not a project dependency. Run with a local Chrome:
//   npm i --no-save puppeteer-core && node scripts/og/render.mjs
// CHROME=/path/to/chrome overrides the default macOS location.
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import puppeteer from "puppeteer-core"

const here = dirname(fileURLToPath(import.meta.url))
const out = resolve(here, "..", "..", "public")
const browser = await puppeteer.launch({
  executablePath:
    process.env.CHROME ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--allow-file-access-from-files"],
})
const page = await browser.newPage()
await page.setViewport({ width: 1200, height: 630 })
await page.goto(pathToFileURL(join(here, "og.html")).href)
await page.evaluate(() => document.fonts.ready)
await page.screenshot({ path: join(out, "og-image.png") })
for (const [name, size] of [
  ["apple-touch-icon.png", 180],
  ["icon-192.png", 192],
  ["icon-512.png", 512],
]) {
  await page.setViewport({
    width: 512,
    height: 512,
    deviceScaleFactor: size / 512,
  })
  await page.goto(pathToFileURL(join(here, "icon.html")).href)
  await page.screenshot({ path: join(out, name) })
}
await browser.close()
