export type KnowledgePoint = {
  kp_id: string;
  video_id: string;
  type: string;
  statement: string;
  evidence_quote: string;
  start_s: number;
  end_s: number;
  confidence: number;
};

export type KnowledgeFile = {
  video_id: string;
  points: KnowledgePoint[];
};

const TYPE_LABEL: Record<string, string> = {
  concept_definition: "概念",
  clause_interpretation: "条文",
  pathomechanism: "病机",
  diagnostic_rule: "辨证",
  treatment_principle: "治则",
  formula_indication: "方证",
  formula_composition: "方义",
  herb_property: "药性",
  clinical_tip: "临证",
  contraindication: "禁忌",
  prognosis: "预后",
  study_method: "学法",
  acupoint_usage: "穴位",
};

export function typeLabel(type: string): string {
  return TYPE_LABEL[type] || "主张";
}

const cache = new Map<string, KnowledgeFile | null>();
const inflight = new Map<string, Promise<KnowledgeFile | null>>();

/** How far (seconds) a KP may sit from t and still count as「附近」. */
export const NEAR_WINDOW_S = 45;
/** Max claims shown in「问这句」sheet. */
export const MAX_CLAIMS = 3;

function normalize(videoId: string, data: KnowledgeFile): KnowledgeFile {
  const points = (Array.isArray(data.points) ? data.points : [])
    .filter((p) => p && typeof p.statement === "string" && p.statement.trim())
    .map((p, i) => {
      const start = Number(p.start_s) || 0;
      let end = Number(p.end_s) || start;
      if (end < start) end = start;
      return {
        kp_id: String(p.kp_id || `${videoId}.kp${i}`),
        video_id: String(p.video_id || videoId),
        type: String(p.type || "claim"),
        statement: String(p.statement).trim(),
        evidence_quote: String(p.evidence_quote || "").trim(),
        start_s: start,
        end_s: end,
        confidence: Number(p.confidence) || 0,
      };
    })
    .sort((a, b) => a.start_s - b.start_s || a.end_s - b.end_s);
  return { video_id: data.video_id || videoId, points };
}

/** Fetch slim public knowledge JSON; caches success and 404. */
export async function loadKnowledgePoints(
  videoId: string,
): Promise<KnowledgeFile | null> {
  if (!videoId) return null;
  if (cache.has(videoId)) return cache.get(videoId) ?? null;
  const pending = inflight.get(videoId);
  if (pending) return pending;

  const job = (async () => {
    try {
      const res = await fetch(`/knowledge/${encodeURIComponent(videoId)}.json`);
      if (!res.ok) {
        cache.set(videoId, null);
        return null;
      }
      const data = (await res.json()) as KnowledgeFile;
      if (!data || !Array.isArray(data.points)) {
        cache.set(videoId, null);
        return null;
      }
      const normalized = normalize(videoId, data);
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

function overlaps(p: KnowledgePoint, t: number): boolean {
  return t >= p.start_s && t <= p.end_s;
}

function distance(p: KnowledgePoint, t: number): number {
  if (overlaps(p, t)) return 0;
  if (t < p.start_s) return p.start_s - t;
  return t - p.end_s;
}

/**
 * Pick claims near the current sentence time.
 * Prefer overlapping windows, then nearest within NEAR_WINDOW_S; cap at MAX_CLAIMS.
 * Empty array = honest「还没核对过」— never invent options.
 */
export function pickClaimsNear(
  points: KnowledgePoint[],
  t: number,
  opts?: { nearWindowS?: number; max?: number },
): KnowledgePoint[] {
  if (!points.length) return [];
  const nearWindow = opts?.nearWindowS ?? NEAR_WINDOW_S;
  const max = opts?.max ?? MAX_CLAIMS;
  const time = Math.max(0, t);

  const scored = points
    .map((p) => ({ p, d: distance(p, time) }))
    .filter((x) => x.d <= nearWindow)
    .sort((a, b) => {
      if (a.d !== b.d) return a.d - b.d;
      if (b.p.confidence !== a.p.confidence) return b.p.confidence - a.p.confidence;
      return a.p.start_s - b.p.start_s;
    });

  const out: KnowledgePoint[] = [];
  const seen = new Set<string>();
  for (const { p } of scored) {
    if (seen.has(p.kp_id)) continue;
    seen.add(p.kp_id);
    out.push(p);
    if (out.length >= max) break;
  }
  return out;
}
