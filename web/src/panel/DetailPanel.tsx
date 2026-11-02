import type { Selection, Subgraph } from "../types";
import { categoryCaption, styleForPred } from "../graph/styleRegistry";
import { CiteLinks, formatT } from "./format";
import { HeldList } from "./HeldList";

const REVIEW_LABEL: Record<string, string> = {
  lexicon: "词典",
  candidate: "候选",
  approved: "已核",
};

function reviewLabel(status: string): string {
  return REVIEW_LABEL[status] ?? status;
}

type Props = {
  subgraph: Subgraph | null;
  selection: Selection | null;
  onClear: () => void;
};

export function DetailPanel({ subgraph, selection, onClear }: Props) {
  if (!subgraph) {
    return (
      <aside className="panel">
        <div className="panel-bar">
          <h2 className="panel-h">详情</h2>
        </div>
        <div className="panel-body">
          <p className="muted">子图还没有加载。</p>
        </div>
      </aside>
    );
  }
  const node =
    selection?.kind === "node"
      ? subgraph.nodes.find((item) => item.id === selection.id)
      : undefined;
  const edge =
    selection?.kind === "edge"
      ? subgraph.edges.find((item) => item.id === selection.id)
      : undefined;
  const held = node
    ? subgraph.held.filter(
        (row) => row.subj_ids.includes(node.id) || row.obj_ids.includes(node.id),
      )
    : subgraph.held;

  const title = node?.label || (edge ? styleForPred(edge.pred).label : "详情");

  return (
    <aside className="panel">
      <div className="panel-bar">
        <h2 className="panel-h">{title}</h2>
        <button type="button" className="panel-clear" onClick={onClear} disabled={!selection}>
          清除选中
        </button>
      </div>
      <div className="panel-body">
        {!node && !edge && (
          <p className="panel-empty muted">
            点击图中节点或边：查看来源与 evidence，并从讲课边打开真实 YouTube 到秒。
          </p>
        )}
        {node && (
          <>
            <div className="field">
              <p className="field-k">类型</p>
              <div className="badge-row">
                <span className="badge">{categoryCaption(node.category) || node.category}</span>
              </div>
            </div>
            <div className="field">
              <p className="field-k">id</p>
              <p className="field-v mono">{node.id}</p>
            </div>
            <div className="field">
              <p className="field-k">Citations</p>
              {node.citations.length === 0 && (
                <p className="muted">此节点无讲课 cite（词典侧）。</p>
              )}
              <ul className="cite-list">
                {node.citations.map((cite, index) => (
                  <li key={`${cite.kind}-${cite.kp_id ?? "m"}-${index}`} className="cite-card">
                    <div className="cite-meta">
                      <span>
                        {cite.kind === "mention" ? "讲座提及" : cite.kp_id ?? "讲课边"}
                      </span>
                      {cite.start_s != null && <span>t={formatT(cite.start_s)}</span>}
                    </div>
                    {cite.statement && <p>{cite.statement}</p>}
                    {cite.quote && <p className="cite-quote">「{cite.quote}」</p>}
                    <CiteLinks cite={cite} />
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
        {edge && (
          <>
            <div className="field">
              <p className="field-k">关系</p>
              <p className="field-v">{styleForPred(edge.pred).caption}</p>
            </div>
            <div className="field">
              <p className="field-k">审核</p>
              <div className="badge-row">
                <span className="badge">{reviewLabel(edge.review_status)}</span>
                <span className={`badge ${edge.source === "lexicon" ? "is-lex" : "is-lec"}`}>
                  {edge.source === "lexicon" ? "词典" : "讲课"}
                </span>
              </div>
            </div>
            <div className="field">
              <p className="field-k">from → to</p>
              <p className="field-v mono">
                {edge.subj_id} → {edge.obj_id}
              </p>
            </div>
            {edge.source === "lexicon" && (
              <p className="muted">词典里的组成关系，没有讲课时间戳。</p>
            )}
            {edge.statement && (
              <div className="field">
                <p className="field-k">摘要</p>
                <p className="field-v">{edge.statement}</p>
              </div>
            )}
            {edge.evidence_quote && (
              <div className="field">
                <p className="field-k">evidence</p>
                <p className="cite-quote">「{edge.evidence_quote}」</p>
              </div>
            )}
            {edge.kp_id && (
              <div className="field">
                <p className="field-k">kp_id</p>
                <p className="field-v mono">{edge.kp_id}</p>
              </div>
            )}
            {edge.citation && (
              <div className="field">
                <p className="field-k">Citations</p>
                <div className="cite-card">
                  <div className="cite-meta">
                    <span>{edge.citation.kp_id || edge.kp_id || "—"}</span>
                    {edge.citation.start_s != null && (
                      <span>t={formatT(edge.citation.start_s)}</span>
                    )}
                  </div>
                  <CiteLinks cite={edge.citation} />
                </div>
              </div>
            )}
          </>
        )}
        {node && <HeldList held={held} />}
      </div>
    </aside>
  );
}
