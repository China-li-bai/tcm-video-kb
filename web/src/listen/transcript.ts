import { fetchPublishedRows, isNumber, isText } from "./publishAssets";

export type Segment = {
  seq: number;
  start_s: number;
  end_s: number;
  text: string;
};

export type TranscriptFile = {
  video_id: string;
  segments: Segment[];
};

const cache = new Map<string, TranscriptFile | null>();
const inflight = new Map<string, Promise<TranscriptFile | null>>();

export function findSegmentAt(segments: Segment[], t: number): Segment | null {
  if (!segments.length) return null;
  const time = Math.max(0, t);
  // Prefer covering segment; else nearest previous start.
  let lo = 0;
  let hi = segments.length - 1;
  let best = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const s = segments[mid];
    if (s.start_s <= time) {
      best = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  const cand = segments[best];
  if (time >= cand.start_s && time < cand.end_s) return cand;
  // If inside a gap, use the previous (or first if before all).
  if (time < segments[0].start_s) return segments[0];
  return cand;
}

export function findSegmentIndexAt(segments: Segment[], t: number): number {
  const hit = findSegmentAt(segments, t);
  if (!hit) return 0;
  return Math.max(
    0,
    segments.findIndex((s) => s.seq === hit.seq && s.start_s === hit.start_s),
  );
}

/** Fetch compact public transcript JSON; caches success and 404. */
export async function loadTranscript(videoId: string): Promise<TranscriptFile | null> {
  if (!videoId) return null;
  if (cache.has(videoId)) return cache.get(videoId) ?? null;
  const pending = inflight.get(videoId);
  if (pending) return pending;

  const job = (async () => {
    try {
      const rows = await fetchPublishedRows(
        `/transcripts/${encodeURIComponent(videoId)}.json`, videoId, "segments",
        row => isNumber(row.seq) && Number.isInteger(row.seq) && row.seq >= 0 && isText(row.text),
      );
      if (!rows?.length || new Set(rows.map(r => r.seq)).size !== rows.length ||
          rows.some((row, i) => i > 0 && Number(row.start_s) < Number(rows[i - 1].start_s))) {
        cache.set(videoId, null);
        return null;
      }
      const normalized: TranscriptFile = { video_id: videoId, segments: rows as Segment[] };
      cache.set(videoId, normalized);
      return normalized;
    } catch {
      cache.set(videoId, null);
      return null;
    } finally {
      inflight.delete(videoId);
    }
  })();

  inflight.set(videoId, job);
  return job;
}
