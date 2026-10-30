import { EdgeEvent, Graph, NodeEvent, type IElementEvent } from "@antv/g6";
import { useEffect, useRef } from "react";
import type { Selection, Subgraph } from "../types";
import { toGraphData } from "./adapter";
import { styleForCategory, styleForPred } from "./styleRegistry";

type Props = {
  subgraph: Subgraph;
  onSelect: (selection: Selection) => void;
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
        labelFill: "#333333",
        labelBackground: true,
        labelBackgroundFill: "#f3f3f3",
        cursor: "pointer",
      };
      if (spec.lineDash) style.lineDash = spec.lineDash;
      return { id: edge.id, source: edge.source, target: edge.target, data: edge.data, style };
    }),
  };
}

export function GraphApp({ subgraph, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

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
          selected: { lineWidth: 3, stroke: "#111111" },
        },
      },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element"],
      animation: false,
    });

    const selected = { id: "" };
    const mark = (id: string) => {
      if (selected.id && selected.id !== id) graph.setElementState(selected.id, []);
      graph.setElementState(id, "selected");
      selected.id = id;
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
      if (alive) graph.fitView();
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
      graph.destroy();
    };
  }, [subgraph]);

  return <div ref={host} className="canvas" aria-label="方证关系图" />;
}
