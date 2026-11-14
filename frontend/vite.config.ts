import { rmSync } from "node:fs"
import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv, type Plugin } from "vite"

// public/data is a small dev fixture. When the build points at real published
// data (VITE_DATA_BASE_URL), drop the fixture so it never ships.
function dropDevFixture(mode: string): Plugin {
  const env = loadEnv(mode, process.cwd(), "VITE_")
  return {
    name: "drop-dev-fixture",
    apply: "build",
    closeBundle() {
      if (env.VITE_DATA_BASE_URL) rmSync(resolve("dist/data"), { recursive: true, force: true })
    },
  }
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), dropDevFixture(mode)],
  server: { port: 5174, host: true },
  build: { sourcemap: true },
}))
