import { DeskStage } from "../layout/DeskStage";
import { useEffect, useState } from "react";
import { GraphApp } from "../graph/GraphApp";
import { styleForCategory, styleForPred } from "../graph/styleRegistry";
import { ToolFocusBar } from "../layout/ToolFocusBar";
import { useToolFocus } from "../layout/useToolFocus";
import { ApiError, fetchSubgraph } from "../api/client";
import { DetailPanel } from "../panel/DetailPanel";
import { ErrorState } from "../panel/ErrorState";
import type { Selection, Subgraph } from "../types";
import { DEFAULT_FOCUS } from "../types";

const GRAPH_PRESETS = [
  { label: "桂枝汤", focus: "formula.gui_zhi_tang" },
  { label: "太阳中风", focus: "syndrome.tai_yang_zhong_feng" },
  { label: "桂枝", focus: "herb.gui_zhi" },
] as const;

export function GraphPage() {
  const { focus, setFocus } = useToolFocus(DEFAULT_FOCUS);
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
    <DeskStage variant="tool" className="listen-tool-page">
      <ToolFocusBar
        title="方证关系图"
        lead="旁证对照 · 听才是主场；点出处「听原讲」回学一段"
        focus={focus}
        onFocus={setFocus}
        presets={GRAPH_PRESETS}
        sibling={{
          to: `/paths?focus=${encodeURIComponent(
            focus.startsWith("syndrome.") ? focus : "syndrome.tai_yang_bing",
          )}`,
          label: "看路径 →",
        }}
      />

      <div className="shell shell--in-desk">
        <main className="graph-main">
          {loading && <p className="status">正在读取子图…</p>}
          {error && <ErrorState title="关系图暂时打不开" detail={error} />}
          {subgraph && subgraph.nodes.length === 0 && (
            <p className="status">这里还没有可展开的关系。</p>
          )}
          {subgraph && subgraph.nodes.length > 0 && (
            <>
              <GraphApp
                subgraph={subgraph}
                selection={selection}
                onSelect={setSelection}
              />
              <footer className="graph-foot">
                <Legend />
                <span className="foot-hint">
                  点节点 / 边看详情；有讲课出处时优先「听原讲」
                </span>
              </footer>
            </>
          )}
        </main>
        <DetailPanel
          subgraph={subgraph}
          selection={selection}
          onClear={clearSelection}
        />
      </div>
    </DeskStage>
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
