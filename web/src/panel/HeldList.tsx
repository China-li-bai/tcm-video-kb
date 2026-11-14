import { predLabel } from "../graph/styleRegistry";
import type { HeldKP } from "../types";
import { CiteLinks } from "./format";

export function HeldList({ held }: { held: HeldKP[] }) {
  if (!held.length) return null;
  return (
    <section className="held" aria-label="待核对的讲法">
      <h3>再听原讲核对</h3>
      <p className="held-note">这些讲法还没有足够把握画进图里，先保留原句供对照，不作结论。</p>
      <ul>
        {held.map((row) => (
          <li key={row.kp_id}>
            <p className="held-pair">{row.subj_labels.join("、")} → {row.obj_labels.join("、")}</p>
            <p className="panel-context">{predLabel(row.pred)} · 尚待核对</p>
            {row.statement && <p>{row.statement}</p>}
            {row.evidence_quote && <blockquote>{row.evidence_quote}</blockquote>}
            {row.citation && <CiteLinks cite={row.citation} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
