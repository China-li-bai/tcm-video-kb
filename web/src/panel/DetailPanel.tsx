import type { Selection, Subgraph } from "../types";
import { categoryCaption, styleForPred } from "../graph/styleRegistry";
import { CiteLinks } from "./format";
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
};

export function DetailPanel({ subgraph, selection }: Props) {
  if (!subgraph) {
    return (
      <aside className="panel">
        <p className="muted">子图还没有加载。</p>
      </aside>
    );
  }
  const node = selection?.kind === "node"
    ? subgraph.nodes.find((item) => item.id === selection.id)
    : undefined;
  const edge = selection?.kind === "edge"
    ? subgraph.edges.find((item) => item.id === selection.id)
    : undefined;
  const held = node
    ? subgraph.held.filter((row) => row.subj_ids.includes(node.id) || row.obj_ids.includes(node.id))
    : subgraph.held;

  return (
    <aside className="panel">
      {!node && !edge && <p className="muted">点节点或边查看出处。</p>}
      {node && (
        <>
          <p className="badge">{categoryCaption(node.category) || node.category}</p>
          <h2>{node.label}</h2>
          <p className="mono">{node.id}</p>
          {node.citations.length === 0 && <p className="muted">这条节点没有讲课时间戳。</p>}
          <ul className="cite-list">
            {node.citations.map((cite, index) => (
              <li key={`${cite.kind}-${cite.kp_id ?? "m"}-${index}`}>
                <p className="muted">{cite.kind === "mention" ? "讲座提及" : `讲课边 ${cite.kp_id ?? ""}`}</p>
                {cite.statement && <p>{cite.statement}</p>}
                {cite.quote && <blockquote>{cite.quote}</blockquote>}
                <CiteLinks cite={cite} />
              </li>
            ))}
          </ul>
        </>
      )}
      {edge && (
        <>
          <p className="badge">{reviewLabel(edge.review_status)}</p>
          <h2>{styleForPred(edge.pred).caption}</h2>
          <p className="mono">
            {edge.subj_id} → {edge.obj_id}
          </p>
          {edge.source === "lexicon" && <p>词典里的组成关系，没有讲课时间戳。</p>}
          {edge.statement && <p>{edge.statement}</p>}
          {edge.evidence_quote && <blockquote>{edge.evidence_quote}</blockquote>}
          {edge.kp_id && <p className="muted">{edge.kp_id}</p>}
          {edge.citation && <CiteLinks cite={edge.citation} />}
        </>
      )}
      {node && <HeldList held={held} />}
    </aside>
  );
}
