import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { ApiError, fetchSubgraph } from "../api/client";
import { GraphApp } from "../graph/GraphApp";
import { styleForCategory, styleForPred } from "../graph/styleRegistry";
import { DetailPanel } from "../panel/DetailPanel";
import { ErrorState } from "../panel/ErrorState";
import type { Selection, Subgraph } from "../types";
import type { ShellContext } from "../App";

export function GraphPage() {
  const { focus } = useOutletContext<ShellContext>();
  const [subgraph, setSubgraph] = useState<Subgraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selection, setSelection] = useState<Selection | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    setError(null);
    setSubgraph(null);
    fetchSubgraph(focus)
      .then((body) => {
        if (ac.signal.aborted) return;
        setSubgraph(body);
        setSelection({ kind: "node", id: body.focus });
      })
      .catch((err: unknown) => {
        if (ac.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : "接口没有返回子图";
        setError(message);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, [focus]);

  return (
    <div className="shell">
      <main>
        {loading && <p className="status">正在读取子图…</p>}
        {error && <ErrorState title="关系图接口不可用" detail={error} />}
        {subgraph && subgraph.nodes.length === 0 && <p className="status">子图是空的。</p>}
        {subgraph && subgraph.nodes.length > 0 && (
          <>
            <GraphApp subgraph={subgraph} onSelect={setSelection} />
            <Legend />
          </>
        )}
      </main>
      <DetailPanel subgraph={subgraph} selection={selection} />
    </div>
  );
}

function Legend() {
  const nodes = ["formula", "herb", "syndrome", "symptom", "pulse"] as const;
  const edges = ["composed_of", "treats", "indicates"] as const;
  return (
    <ul className="legend">
      {nodes.map((category) => {
        const spec = styleForCategory(category);
        return (
          <li key={category}>
            <i
              className={`swatch shape-${spec.shape}`}
              style={{
                background: spec.fill,
                borderColor: spec.stroke,
                borderStyle: spec.lineDash ? "dashed" : "solid",
              }}
            />
            {spec.badge}
          </li>
        );
      })}
      {edges.map((pred) => {
        const spec = styleForPred(pred);
        return (
          <li key={pred}>
            <i className="line" style={{ borderTopStyle: spec.lineDash ? "dashed" : "solid" }} />
            {spec.caption}
          </li>
        );
      })}
    </ul>
  );
}
