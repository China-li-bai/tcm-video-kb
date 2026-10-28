/**
 * Grayscale shapes for the formula-pattern graph.
 * Categories differ by shape and gray value. Do not hard-code a 国风 palette.
 */

export type NodeStyleSpec = {
  shape: "rect" | "ellipse" | "diamond";
  fill: string;
  stroke: string;
  labelFill: string;
  size: [number, number];
  radius: number;
  lineDash?: number[];
  badge: string;
};

export type EdgeStyleSpec = {
  stroke: string;
  lineWidth: number;
  lineDash?: number[];
  label: string;
  caption: string;
};

const STYLES: Record<string, NodeStyleSpec> = {
  formula: {
    shape: "rect",
    fill: "#1c1c1c",
    stroke: "#1c1c1c",
    labelFill: "#f7f7f7",
    size: [132, 52],
    radius: 8,
    badge: "方",
  },
  herb: {
    shape: "rect",
    fill: "#ffffff",
    stroke: "#222222",
    labelFill: "#1a1a1a",
    size: [108, 44],
    radius: 8,
    badge: "药",
  },
  syndrome: {
    shape: "diamond",
    fill: "#e6e6e6",
    stroke: "#222222",
    labelFill: "#1a1a1a",
    size: [148, 76],
    radius: 0,
    badge: "证",
  },
  symptom: {
    shape: "ellipse",
    fill: "#fafafa",
    stroke: "#222222",
    labelFill: "#1a1a1a",
    size: [104, 52],
    radius: 0,
    badge: "症",
  },
  pulse: {
    shape: "ellipse",
    fill: "#ffffff",
    stroke: "#222222",
    labelFill: "#1a1a1a",
    size: [104, 52],
    radius: 0,
    lineDash: [5, 4],
    badge: "脉",
  },
  tongue: {
    shape: "ellipse",
    fill: "#ffffff",
    stroke: "#222222",
    labelFill: "#1a1a1a",
    size: [104, 52],
    radius: 0,
    lineDash: [2, 3],
    badge: "舌",
  },
  concept: {
    shape: "rect",
    fill: "#ffffff",
    stroke: "#222222",
    labelFill: "#1a1a1a",
    size: [120, 48],
    radius: 4,
    lineDash: [4, 3],
    badge: "概念",
  },
};

const FALLBACK: NodeStyleSpec = {
  shape: "rect",
  fill: "#ffffff",
  stroke: "#222222",
  labelFill: "#1a1a1a",
  size: [112, 44],
  radius: 6,
  badge: "",
};

export function styleForCategory(category: string): NodeStyleSpec {
  return STYLES[category] ?? FALLBACK;
}

/**
 * Display names for edge predicates. The graph and legend read `label`;
 * API / JSON keep the English key (`composed_of`, `treats`, `indicates`).
 */
const PRED_LABEL: Record<string, string> = {
  composed_of: "组成",
  treats: "主治",
  indicates: "提示",
  on_meridian: "归经",
  belongs_to: "属于",
  contraindicated: "禁忌",
  related: "相关",
};

export function predLabel(pred: string): string {
  return PRED_LABEL[pred] ?? "关系";
}

export function styleForPred(pred: string): EdgeStyleSpec {
  const label = predLabel(pred);
  switch (pred) {
    case "composed_of":
      return { stroke: "#333333", lineWidth: 1.5, label, caption: "组成（方 → 药）" };
    case "treats":
      return { stroke: "#111111", lineWidth: 2, label, caption: "主治（方 → 证）" };
    case "indicates":
      return {
        stroke: "#333333",
        lineWidth: 1.5,
        lineDash: [6, 4],
        label,
        caption: "提示（症/脉/舌 → 证）",
      };
    default:
      return { stroke: "#666666", lineWidth: 1, label, caption: label };
  }
}

export function categoryCaption(category: string): string {
  return styleForCategory(category).badge || category;
}
