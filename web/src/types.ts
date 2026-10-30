export const DEFAULT_FOCUS = "formula.gui_zhi_tang";

export type Citation = {
  kind?: string;
  kp_id?: string | null;
  video_id?: string | null;
  start_s?: number | null;
  end_s?: number | null;
  quote?: string | null;
  title?: string | null;
  statement?: string | null;
  t_url?: string | null;
  youtube_t_url?: string | null;
};

export type GraphNode = {
  id: string;
  label: string;
  category: string;
  citations: Citation[];
};

export type GraphEdge = {
  id: string;
  subj_id: string;
  pred: string;
  obj_id: string;
  source: string;
  kp_id?: string | null;
  citation?: Citation | null;
  confidence?: number | null;
  review_status: string;
  evidence_quote?: string | null;
  statement?: string | null;
  video_id?: string | null;
};

export type HeldKP = {
  kp_id: string;
  video_id: string;
  kp_type: string;
  pred: string;
  subj_ids: string[];
  obj_ids: string[];
  subj_labels: string[];
  obj_labels: string[];
  reasons: string[];
  confidence?: number | null;
  evidence_quote?: string;
  statement?: string;
  citation?: Citation | null;
};

export type Subgraph = {
  focus: string;
  disclaimer: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  held: HeldKP[];
};

export type PathCard = {
  subj_id: string;
  obj_id: string;
  label: string;
  category: string;
  pred: string;
  kp_id: string;
  review_status: string;
  evidence_quote?: string | null;
  statement?: string;
  video_id?: string | null;
  start_s?: number | null;
  t_url?: string | null;
  youtube_t_url?: string | null;
  title?: string | null;
};

export type PathTrack = {
  syndrome_id: string;
  label: string;
  treats: PathCard[];
  cards: PathCard[];
};

export type PathsResponse = {
  focus: string;
  disclaimer: string;
  equal_weight: boolean;
  tracks: PathTrack[];
  held: HeldKP[];
};

export type Selection = { kind: "node" | "edge"; id: string };
