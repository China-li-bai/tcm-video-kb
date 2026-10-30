import supplement from "../../data/fangzhengPathsSupplement.json";
import type { PathCard, PathTrack, PathsResponse } from "../../types";

export type CiteItem = {
  kp_id?: string | null;
  url?: string | null;
  start_s?: number | null;
  evidence?: string | null;
  youtube_t_url?: string | null;
  t_url?: string | null;
};

export type PathStep = {
  kind: string;
  label: string;
  ids?: string[];
};

export type UiTrack = {
  id: string;
  label: string;
  layer?: string;
  summary?: string;
  origin: "api" | "demo";
};

export type UiHypothesis = {
  id: string;
  track_id: string;
  title: string;
  target_label: string;
  path_summary: string;
  path_steps: PathStep[];
  symptom_ids: string[];
  source_layers: string[];
  citations: CiteItem[];
  origin: "api" | "demo";
};

export type SymFilter = { id: string; label: string };

export type PathsViewModel = {
  tracks: UiTrack[];
  hypotheses: UiHypothesis[];
  symptomFilters: SymFilter[];
  disclaimer: string;
  usedDemoSupplement: boolean;
  usedApi: boolean;
  held: PathsResponse["held"];
};

const KIND_ZH: Record<string, string> = {
  formula: "方",
  syndrome: "证",
  symptom: "症",
  pulse: "脉",
  herb: "药",
  concept: "概念",
  tongue: "舌",
};

export function kindZh(kind: string): string {
  return KIND_ZH[kind] || kind;
}

function cardCite(card: PathCard): CiteItem {
  return {
    kp_id: card.kp_id,
    start_s: card.start_s ?? null,
    evidence: card.evidence_quote ?? card.statement ?? null,
    youtube_t_url: card.youtube_t_url ?? null,
    t_url: card.t_url ?? null,
    url: card.youtube_t_url ?? null,
  };
}

/** Build equal-weight path cards from API syndrome tracks. */
function hypothesesFromApi(data: PathsResponse): { tracks: UiTrack[]; hyps: UiHypothesis[]; filters: SymFilter[] } {
  const tracks: UiTrack[] = data.tracks.map((t) => ({
    id: `api.${t.syndrome_id}`,
    label: t.label,
    layer: "讲义",
    summary: "接口证轨：方主治证、症/脉提示证。同权并列，非诊疗。",
    origin: "api" as const,
  }));

  const hyps: UiHypothesis[] = data.tracks.map((t) => apiTrackToHyp(t, data.focus));
  const filters = deriveFilters(data.tracks);
  return { tracks, hyps, filters };
}

function apiTrackToHyp(track: PathTrack, focus: string): UiHypothesis {
  const treatLabels = track.treats.map((c) => c.label);
  const indicateLabels = track.cards.map((c) => c.label);
  const formulaLabel = treatLabels[0] || (focus.startsWith("formula.") ? focus.split(".").pop() || focus : "—");
  const steps: PathStep[] = [];
  if (indicateLabels.length) {
    steps.push({
      kind: track.cards[0]?.category || "symptom",
      label: indicateLabels.join(" · "),
      ids: track.cards.map((c) => c.subj_id),
    });
  }
  steps.push({ kind: "syndrome", label: track.label, ids: [track.syndrome_id] });
  if (track.treats.length) {
    steps.push({
      kind: "formula",
      label: treatLabels.join(" / "),
      ids: track.treats.map((c) => c.subj_id),
    });
  }
  const cites = [...track.treats, ...track.cards].map(cardCite);
  const symptomIds = track.cards.map((c) => c.subj_id);
  return {
    id: `api.hyp.${track.syndrome_id}`,
    track_id: `api.${track.syndrome_id}`,
    title: `${track.label} → ${formulaLabel}`,
    target_label: `${track.label} / ${formulaLabel}`,
    path_summary:
      (indicateLabels.length ? `${indicateLabels.join(" · ")} → ` : "") +
      `${track.label}` +
      (treatLabels.length ? ` → ${treatLabels.join(" / ")}` : ""),
    path_steps: steps,
    symptom_ids: symptomIds,
    source_layers: ["讲义"],
    citations: cites,
    origin: "api",
  };
}

function deriveFilters(tracks: PathTrack[]): SymFilter[] {
  const seen = new Map<string, string>();
  for (const t of tracks) {
    for (const c of t.cards) {
      if (!seen.has(c.subj_id)) seen.set(c.subj_id, c.label);
    }
  }
  return [...seen.entries()].map(([id, label]) => ({ id, label }));
}

function demoApplies(focus: string): boolean {
  return (supplement.applies_to_focus as string[]).includes(focus);
}

function demoBundle(): { tracks: UiTrack[]; hyps: UiHypothesis[]; filters: SymFilter[] } {
  const tracks: UiTrack[] = (supplement.tracks as Array<{ id: string; label: string; layer?: string; summary?: string }>).map(
    (t) => ({
      id: t.id,
      label: t.label,
      layer: t.layer,
      summary: t.summary,
      origin: "demo" as const,
    }),
  );
  const hyps: UiHypothesis[] = (supplement.hypotheses as Array<{
    id: string;
    track_id: string;
    title: string;
    target_label: string;
    path_summary: string;
    path_steps: PathStep[];
    symptom_ids: string[];
    source_layers: string[];
    citations: CiteItem[];
  }>).map((h) => ({
    id: h.id,
    track_id: h.track_id,
    title: h.title,
    target_label: h.target_label,
    path_summary: h.path_summary,
    path_steps: h.path_steps || [],
    symptom_ids: h.symptom_ids || [],
    source_layers: h.source_layers || [],
    origin: "demo" as const,
    citations: (h.citations || []).map((c) => ({
      ...c,
      youtube_t_url: c.url ?? c.youtube_t_url ?? null,
    })),
  }));
  const filters = supplement.symptom_filters as SymFilter[];
  return { tracks, hyps, filters };
}

/**
 * Merge API paths with readonly prototype supplement for 桂枝汤.
 * Demo cards are marked origin=demo; API cards origin=api.
 */
export function buildPathsViewModel(data: PathsResponse): PathsViewModel {
  const api = hypothesesFromApi(data);
  const useDemo = demoApplies(data.focus);
  const demo = useDemo ? demoBundle() : null;

  const trackMap = new Map<string, UiTrack>();
  if (demo) {
    for (const t of demo.tracks) trackMap.set(t.id, t);
  }
  for (const t of api.tracks) {
    if (!trackMap.has(t.id)) trackMap.set(t.id, t);
  }

  const hypMap = new Map<string, UiHypothesis>();
  if (demo) {
    for (const h of demo.hyps) hypMap.set(h.id, h);
  }
  // Prefer demo when both present for same pedagogical track; still append distinct API hyps
  for (const h of api.hyps) {
    if (!hypMap.has(h.id)) hypMap.set(h.id, h);
  }

  let filters: SymFilter[] = [];
  if (demo?.filters.length) filters = demo.filters;
  else filters = api.filters;

  // If demo filters exist, keep them; also add any API-derived ids not already present
  if (demo?.filters.length && api.filters.length) {
    const have = new Set(filters.map((f) => f.id));
    for (const f of api.filters) {
      if (!have.has(f.id)) filters.push(f);
    }
  }

  return {
    tracks: [...trackMap.values()],
    hypotheses: [...hypMap.values()],
    symptomFilters: filters,
    disclaimer: data.disclaimer,
    usedDemoSupplement: Boolean(demo),
    usedApi: api.hyps.length > 0,
    held: data.held,
  };
}

export function evidenceCount(h: UiHypothesis): number {
  return h.citations?.length || 0;
}

export { supplement };
