import type { Selection, Subgraph } from "../types";
import { styleForCategory, styleForPred } from "../graph/styleRegistry";
import { EvidenceExcerpt } from "./EvidenceExcerpt";
import { HeldList } from "./HeldList";

const REVIEW_LABEL: Record<string, string> = {
  lexicon: "词典整理",
  candidate: "讲课整理，尚待核对",
  approved: "已核对来源",
};

type Props = { subgraph: Subgraph | null; selection: Selection | null; onClear: () => void };

export function DetailPanel({ subgraph, selection, onClear }: Props) {
  const node = selection?.kind === "node" ? subgraph?.nodes.find((n) => n.id === selection.id) : undefined;
  const edge = selection?.kind === "edge" ? subgraph?.edges.find((e) => e.id === selection.id) : undefined;
  const held = node ? subgraph!.held.filter((row) => row.subj_ids.includes(node.id) || row.obj_ids.includes(node.id)) : subgraph?.held ?? [];
  const label = (id: string) => subgraph?.nodes.find((n) => n.id === id)?.label || "相关条目";
  const title = node?.label || (edge ? styleForPred(edge.pred).label : "讲法与出处");

  return (
    <aside className="panel" aria-label="讲法与出处">
      <div className="panel-bar">
        <h2 className="panel-h">{title}</h2>
        <button type="button" className="panel-clear" onClick={onClear} disabled={!selection}>清除选中</button>
      </div>
      <div className="panel-body">
        {!subgraph && <p className="muted">关系图还没有加载。</p>}
        {subgraph && !node && !edge && <p className="panel-empty muted">点图中的条目或连线看讲法与出处，再听一听原讲。</p>}
        {node && <>
          <p className="panel-context">{styleForCategory(node.category).badge || "条目"} · 讲法与出处</p>
          <section className="field">
            <h3 className="field-k">原讲出处</h3>
            {node.citations.length === 0 && <p className="muted">词典条目，暂未找到对应的原讲片段。</p>}
            <ul className="cite-list">
              {node.citations.map((cite, index) => <li key={`${cite.kind}-${cite.kp_id ?? "m"}-${index}`}>
                <EvidenceExcerpt cite={cite} statement={cite.statement} quote={cite.quote} />
              </li>)}
            </ul>
          </section>
        </>}
        {edge && <>
          <section className="field">
            <h3 className="field-k">{styleForPred(edge.pred).caption}</h3>
            <p className="field-v">{label(edge.subj_id)} → {label(edge.obj_id)}</p>
            <p className="panel-context">{REVIEW_LABEL[edge.review_status] ?? "来源尚待核对"}</p>
          </section>
          {edge.source === "lexicon" && <p className="muted">这条关系来自词典，暂无对应的原讲片段。</p>}
          {edge.citation ? <EvidenceExcerpt cite={edge.citation} statement={edge.statement} quote={edge.evidence_quote} /> : <>
            {edge.statement && <p className="evidence-statement">{edge.statement}</p>}
            {edge.evidence_quote && <p className="cite-quote">「{edge.evidence_quote}」</p>}
          </>}
        </>}
        {node && <HeldList held={held} />}
      </div>
    </aside>
  );
}
