import type { Subgraph } from "../types";

/** API subgraph → plain graph data. Colors stay in the style registry. */
export type GraphData = {
  nodes: { id: string; data: { label: string; category: string } }[];
  edges: { id: string; source: string; target: string; data: { pred: string } }[];
};

export function toGraphData(subgraph: Subgraph): GraphData {
  return {
    nodes: subgraph.nodes.map((node) => ({
      id: node.id,
      data: { label: node.label, category: node.category },
    })),
    edges: subgraph.edges.map((edge) => ({
      id: edge.id,
      source: edge.subj_id,
      target: edge.obj_id,
      data: { pred: edge.pred },
    })),
  };
}
