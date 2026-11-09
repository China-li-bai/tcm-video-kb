/** Runtime boundary: untrusted HTTP bodies never become timed learning data
 * through coercion/defaults. Missing/unusable data is null, not an empty success.
 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
export function isText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
export function hasWindow(row: Record<string, unknown>): boolean {
  return isNumber(row.start_s) && isNumber(row.end_s) && row.start_s >= 0 && row.end_s >= row.start_s;
}

export async function fetchPublishedRows(
  url: string, videoId: string, key: string,
  validate: (row: Record<string, unknown>) => boolean,
): Promise<Record<string, unknown>[] | null> {
  const res = await fetch(url);
  const mediaType = (res.headers.get('content-type') ?? '').split(';')[0].trim().toLowerCase();
  if (!res.ok || !(mediaType === 'application/json' || /^application\/[\w.-]+\+json$/.test(mediaType))) return null;
  const data: unknown = await res.json();
  if (!isRecord(data) || data.video_id !== videoId) return null;
  const rows = data[key];
  if (!Array.isArray(rows) || !rows.every(row => isRecord(row) && hasWindow(row) && validate(row))) return null;
  return rows;
}
