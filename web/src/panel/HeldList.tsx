import { predLabel } from "../graph/styleRegistry";
import type { HeldKP } from "../types";
import { CiteLinks } from "./format";

export function HeldList({ held }: { held: HeldKP[] }) {
  if (!held.length) return null;
  return (
    <section className="held">
      <h3>未入图（未过硬闸）</h3>
      <ul>
        {held.map((row) => (
          <li key={row.kp_id}>
            <p className="held-pair">
              {row.subj_labels.join("、")} → {row.obj_labels.join("、")}
            </p>
            <p className="muted">
              {row.kp_id} · {predLabel(row.pred)} · {row.reasons.join("；")}
            </p>
            {row.statement && <p>{row.statement}</p>}
            {row.evidence_quote && <blockquote>{row.evidence_quote}</blockquote>}
            {row.citation && <CiteLinks cite={row.citation} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
