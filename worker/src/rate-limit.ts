/**
 * D1-backed fixed-window rate limiter.
 *
 * Chosen over the Workers Rate Limiting binding because it is deterministic under
 * miniflare (testable), needs no extra binding for the owner to configure, and
 * volumes here are tiny. Tradeoff: one D1 write per limited request, and a fixed
 * window allows up to 2x the limit across a window boundary. Rows older than a day
 * are purged opportunistically.
 */
export const HOUR_S = 3600;

export async function hit(
  db: D1Database,
  bucket: string,
  subject: string,
  limit: number,
  windowSeconds = HOUR_S,
  nowMs = Date.now(),
): Promise<{ allowed: boolean; count: number }> {
  const nowS = Math.floor(nowMs / 1000);
  const windowStart = nowS - (nowS % windowSeconds);
  const key = `${bucket}:${subject}:${windowStart}`;
  const row = await db
    .prepare(
      `INSERT INTO rate_limits (key, window_start, count) VALUES (?1, ?2, 1)
       ON CONFLICT(key) DO UPDATE SET count = count + 1
       RETURNING count`,
    )
    .bind(key, windowStart)
    .first<{ count: number }>();
  const count = row?.count ?? 1;
  if (Math.random() < 0.02) {
    await db.prepare("DELETE FROM rate_limits WHERE window_start < ?1").bind(nowS - 86400).run();
  }
  return { allowed: count <= limit, count };
}

export const num = (v: string | undefined, fallback: number): number => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : fallback;
};
