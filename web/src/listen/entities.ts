import { fetchPublishedRows, isNumber, isText } from "./publishAssets";

export type EntityMention = {
  entity_id: string;
  label: string;
  type: string;
  start_s: number;
  end_s: number;
  seq?: number | null;
};

export type EntitiesFile = {
  video_id: string;
  mentions: EntityMention[];
};

/** Chinese badge for chip / sheet — never show English type codes in UI. */
const TYPE_BADGE: Record<string, string> = {
  formula: "方",
  herb: "药",
  symptom: "症",
  pattern: "证",
  syndrome: "证",
  six_channel: "六经",
  disease: "病",
  zangfu: "脏腑",
  pulse: "脉",
  tongue: "舌",
  clause: "条文",
  meridian: "经",
  acupoint: "穴",
};

export function entityTypeBadge(type: string): string {
  return TYPE_BADGE[type] || "名";
}

/** Types that usually resolve in the G6 方证图 focus API. */
const GRAPHABLE = new Set([
  "formula",
  "herb",
  "symptom",
  "pattern",
  "syndrome",
  "pulse",
  "tongue",
]);

export function isGraphableEntity(m: EntityMention): boolean {
  if (!m.entity_id || m.entity_id.startsWith("new.")) return false;
  const prefix = m.entity_id.split(".")[0];
  return (
    GRAPHABLE.has(m.type) ||
    prefix === "formula" ||
    prefix === "herb" ||
    prefix === "symptom" ||
    prefix === "syndrome" ||
    prefix === "pulse" ||
    prefix === "tongue"
  );
}

const cache = new Map<string, EntitiesFile | null>();
const inflight = new Map<string, Promise<EntitiesFile | null>>();

/** Overlap / near window for chips (tighter than 问这句 — chips stay sparse). */
export const CHIP_NEAR_S = 6;
/** Max chips on the active sentence. */
export const MAX_CHIPS = 3;

/** Fetch slim public entities JSON; caches success and 404. */
export async function loadEntities(
  videoId: string,
): Promise<EntitiesFile | null> {
  if (!videoId) return null;
  if (cache.has(videoId)) return cache.get(videoId) ?? null;
  const pending = inflight.get(videoId);
  if (pending) return pending;

  const job = (async () => {
    try {
      const rows = await fetchPublishedRows(
        `/entities/${encodeURIComponent(videoId)}.json`, videoId, "mentions",
        row => isText(row.entity_id) && isText(row.label) && isText(row.type) &&
          (row.seq == null || (isNumber(row.seq) && Number.isInteger(row.seq) && row.seq >= 0)),
      );
      if (!rows || new Set(rows.map(r => `${r.entity_id}:${r.start_s}`)).size !== rows.length) {
        cache.set(videoId, null);
        return null;
      }
      const normalized: EntitiesFile = {
        video_id: videoId,
        mentions: (rows as EntityMention[]).sort((a, b) => a.start_s - b.start_s || a.end_s - b.end_s),
      };
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

function overlapsWindow(
  m: EntityMention,
  lo: number,
  hi: number,
): boolean {
  return m.start_s < hi && m.end_s > lo;
}

function distanceToWindow(m: EntityMention, lo: number, hi: number): number {
  if (overlapsWindow(m, lo, hi)) return 0;
  if (m.end_s <= lo) return lo - m.end_s;
  return m.start_s - hi;
}

/**
 * Pick sparse high-conf entity chips for the active sentence window.
 * Empty = stay quiet (no inventing). Dedupes by entity_id.
 */
export function pickChipsNear(
  mentions: EntityMention[],
  startS: number,
  endS?: number,
  opts?: { nearWindowS?: number; max?: number },
): EntityMention[] {
  if (!mentions.length) return [];
  const nearWindow = opts?.nearWindowS ?? CHIP_NEAR_S;
  // A cap counts whole items; zero/invalid caps must not leak a first result.
  const max = Math.floor(opts?.max ?? MAX_CHIPS);
  if (!Number.isFinite(max) || max <= 0) return [];
  const lo = Math.max(0, startS);
  const hi = Math.max(lo + 0.5, endS ?? startS + 4);

  const scored = mentions
    .map((m) => ({ m, d: distanceToWindow(m, lo, hi) }))
    .filter((x) => x.d <= nearWindow)
    .sort((a, b) => {
      if (a.d !== b.d) return a.d - b.d;
      // Prefer 方/证/症 first among ties.
      const rank = (t: string) =>
        ({ formula: 0, pattern: 1, syndrome: 1, symptom: 2, herb: 3 } as Record<
          string,
          number
        >)[t] ?? 9;
      const ra = rank(a.m.type);
      const rb = rank(b.m.type);
      if (ra !== rb) return ra - rb;
      return a.m.start_s - b.m.start_s;
    });

  const out: EntityMention[] = [];
  const seen = new Set<string>();
  for (const { m } of scored) {
    if (seen.has(m.entity_id)) continue;
    seen.add(m.entity_id);
    out.push(m);
    if (out.length >= max) break;
  }
  return out;
}
