import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { ApiError, fetchSubgraph } from "../api/client";
import { GraphApp } from "../graph/GraphApp";
import { styleForCategory, styleForPred } from "../graph/styleRegistry";
import { DetailPanel } from "../panel/DetailPanel";
import { ErrorState } from "../panel/ErrorState";
import type { Selection, Subgraph } from "../types";
import type { ShellContext } from "../layout/AppShell";

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

  function clearSelection() {
    setSelection(null);
  }

  return (
    <div className="shell">
      <main className="graph-main">
        {loading && <p className="status">正在读取子图…</p>}
        {error && <ErrorState title="关系图接口不可用" detail={error} />}
        {subgraph && subgraph.nodes.length === 0 && <p className="status">子图是空的。</p>}
        {subgraph && subgraph.nodes.length > 0 && (
          <>
            <GraphApp subgraph={subgraph} selection={selection} onSelect={setSelection} />
            <footer className="graph-foot">
              <Legend />
              <span className="foot-hint">点节点 / 边看详情；点「听原讲」进站内学一段（YouTube 为退路）</span>
            </footer>
          </>
        )}
      </main>
      <DetailPanel subgraph={subgraph} selection={selection} onClear={clearSelection} />
    </div>
  );
}

function Legend() {
  const nodes = ["formula", "herb", "syndrome", "symptom", "pulse", "concept"] as const;
  const edges = ["composed_of", "treats", "indicates", "related"] as const;
  return (
    <div className="legend" aria-label="图例">
      <div className="leg-group" aria-label="节点类型">
        <span className="leg-k">节点</span>
        {nodes.map((category) => {
          const spec = styleForCategory(category);
          return (
            <span key={category} className="leg" title={spec.badge}>
              <i
                className={`swatch shape-${spec.shape}`}
                style={{
                  background: spec.fill,
                  borderColor: spec.stroke,
                  borderStyle: spec.lineDash ? "dashed" : "solid",
                }}
              />
              {spec.badge}
            </span>
          );
        })}
      </div>
      <div className="leg-group" aria-label="关系谓词">
        <span className="leg-k">边</span>
        {edges.map((pred) => {
          const spec = styleForPred(pred);
          return (
            <span key={pred} className="leg">
              <i
                className="line"
                style={{ borderTopStyle: spec.lineDash ? "dashed" : "solid" }}
              />
              {spec.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
