// The Worker source is type-checked here only to derive the Hono client types.
// Its Cloudflare binding types cannot load alongside the DOM lib, so the
// bindings are stubbed loosely; they never appear in request or response shapes.
/* eslint-disable */
interface D1Statement {
  bind(...values: any[]): D1Statement
  first<T = any>(column?: string): Promise<T | null>
  all<T = any>(): Promise<{ results: T[]; meta: any }>
  run<T = any>(): Promise<{ results: T[]; meta: any }>
}
interface D1Database {
  prepare(query: string): D1Statement
  batch<T = any>(statements: D1Statement[]): Promise<T[]>
}
interface R2Bucket {
  put(key: string, value: any, options?: any): Promise<any>
  get(key: string): Promise<any>
  head(key: string): Promise<any>
  delete(key: string): Promise<void>
}
