import { EdgeEvent, Graph, NodeEvent, type IElementEvent } from "@antv/g6";
import { useEffect, useRef } from "react";
import type { Selection, Subgraph } from "../types";
import { toGraphData } from "./adapter";
import { styleForCategory, styleForPred } from "./styleRegistry";

type Props = {
  subgraph: Subgraph;
  selection: Selection | null;
  onSelect: (selection: Selection | null) => void;
};

function paint(subgraph: Subgraph) {
  const data = toGraphData(subgraph);
  return {
    nodes: data.nodes.map((node) => {
      const spec = styleForCategory(node.data.category);
      const style: Record<string, unknown> = {
        size: spec.size,
        fill: spec.fill,
        stroke: spec.stroke,
        lineWidth: 1.5,
        radius: spec.radius,
        labelText: node.data.label,
        labelFill: spec.labelFill,
        labelFontSize: 14,
        labelFontWeight: 600,
        labelPlacement: "center",
        cursor: "pointer",
      };
      if (spec.lineDash) style.lineDash = spec.lineDash;
      return { id: node.id, type: spec.shape, data: node.data, style };
    }),
    edges: data.edges.map((edge) => {
      const spec = styleForPred(edge.data.pred);
      const style: Record<string, unknown> = {
        stroke: spec.stroke,
        lineWidth: spec.lineWidth,
        endArrow: true,
        labelText: spec.label,
        labelFontSize: 11,
        labelFill: "#8F959E",
        labelBackground: true,
        labelBackgroundFill: "#F5F6F8",
        cursor: "pointer",
      };
      if (spec.lineDash) style.lineDash = spec.lineDash;
      return { id: edge.id, source: edge.source, target: edge.target, data: edge.data, style };
    }),
  };
}

export function GraphApp({ subgraph, selection, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const graphRef = useRef<Graph | null>(null);
  const selectedRef = useRef("");

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const graph = new Graph({
      container: el,
      width: el.clientWidth || 800,
      height: el.clientHeight || 640,
      autoFit: "view",
      padding: 28,
      data: paint(subgraph),
      layout: {
        type: "dagre",
        rankdir: "LR",
        nodesep: 28,
        ranksep: 110,
      },
      node: {
        state: {
          selected: { lineWidth: 2.5, stroke: "#3370FF", fill: "#E8F0FF" }, // 候选待拍板 · soft 蓝选中
        },
      },
      edge: {
        state: {
          selected: { lineWidth: 3, stroke: "#3370FF" }, // 候选待拍板
        },
      },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element"],
      animation: false,
    });
    graphRef.current = graph;

    const mark = (id: string) => {
      if (selectedRef.current && selectedRef.current !== id) {
        try {
          graph.setElementState(selectedRef.current, []);
        } catch {
          /* element may be gone after data swap */
        }
      }
      try {
        graph.setElementState(id, "selected");
      } catch {
        /* ignore */
      }
      selectedRef.current = id;
    };

    const clearMark = () => {
      if (selectedRef.current) {
        try {
          graph.setElementState(selectedRef.current, []);
        } catch {
          /* ignore */
        }
      }
      selectedRef.current = "";
    };

    const elementId = (event: IElementEvent): string | undefined => {
      const id = event.target?.id;
      return typeof id === "string" ? id : undefined;
    };
    graph.on(NodeEvent.CLICK, (event) => {
      const id = elementId(event as IElementEvent);
      if (!id) return;
      mark(id);
      onSelectRef.current({ kind: "node", id });
    });
    graph.on(EdgeEvent.CLICK, (event) => {
      const id = elementId(event as IElementEvent);
      if (!id) return;
      mark(id);
      onSelectRef.current({ kind: "edge", id });
    });

    let alive = true;
    void graph.render().then(() => {
      if (!alive) return;
      graph.fitView();
      if (selection?.id) mark(selection.id);
    });
    let frame = 0;
    const observer = new ResizeObserver(() => {
      if (!alive) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!alive) return;
        graph.resize(el.clientWidth, el.clientHeight);
        void graph.fitView();
      });
    });
    observer.observe(el);
    return () => {
      alive = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      clearMark();
      graphRef.current = null;
      graph.destroy();
    };
    // selection applied in separate effect; only rebuild on subgraph change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subgraph]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const id = selection?.id ?? "";
    if (!id) {
      if (selectedRef.current) {
        try {
          graph.setElementState(selectedRef.current, []);
        } catch {
          /* ignore */
        }
        selectedRef.current = "";
      }
      return;
    }
    if (selectedRef.current && selectedRef.current !== id) {
      try {
        graph.setElementState(selectedRef.current, []);
      } catch {
        /* ignore */
      }
    }
    try {
      graph.setElementState(id, "selected");
      selectedRef.current = id;
    } catch {
      /* ignore */
    }
  }, [selection]);

  return <div ref={host} className="canvas" aria-label="方证关系图" />;
}
