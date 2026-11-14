import { getLecture } from './lectures';

/** Source-defined slugs only; UI additionally requires an actual catalog entry. */
const validId = (value: unknown): value is string =>
  typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value);
export const finiteSeconds = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

/** One request-location contract for search, citations, resume and saved quotes.
 * Missing time opens the lecture; malformed/nonfinite time fails closed. Finite
 * negatives clamp to zero; floor seconds, omitting zero. Not playback telemetry.
 * Shared fixture with Python site_watch_url prevents divergent rounding rules.
 */
export function watchHref(videoId: unknown, startS?: unknown): string | null {
  if (!validId(videoId) || !getLecture(videoId)) return null;
  if (startS != null && !finiteSeconds(startS)) return null;
  const seconds = finiteSeconds(startS) ? Math.max(0, Math.floor(startS)) : 0;
  return `/watch/${videoId}${seconds > 0 ? `?t=${seconds}` : ''}`;
}

function youtubeIdFromUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443')) return null;
    let id: string | null = null;
    if (url.hostname === 'youtu.be') id = url.pathname.slice(1);
    if (['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(url.hostname) && url.pathname === '/watch') {
      const ids = url.searchParams.getAll('v');
      id = ids.length === 1 ? ids[0] : null;
    }
    return validId(id) ? id : null;
  } catch { return null; }
}

type Source = {
  video_id?: string | null;
  start_s?: number | null;
  youtube_id?: string | null;
  url?: string | null;
  youtube_t_url?: string | null;
};
/** Preserve the original platform, but reconstruct allowlisted YouTube links.
 * The catalog is authoritative for known lecture identities. An arbitrary
 * stored t_url, youtube_t_url or url is never returned directly as a link.
 */
export function youtubeHref(cite: Source): string | null {
  const lecture = typeof cite.video_id === 'string' ? getLecture(cite.video_id) : undefined;
  const id = lecture?.youtubeId || (validId(cite.youtube_id) ? cite.youtube_id : null)
    || youtubeIdFromUrl(cite.url) || youtubeIdFromUrl(cite.youtube_t_url);
  if (!validId(id)) return null;
  const seconds = finiteSeconds(cite.start_s) ? Math.max(0, Math.floor(cite.start_s)) : null;
  return `https://www.youtube.com/watch?v=${id}${seconds != null ? `&t=${seconds}s` : ''}`;
}
