import type { Citation } from "../types";
import { CiteLinks } from "./format";

type Props = { cite: Citation; quote?: string | null; statement?: string | null };

/** Shared reading hierarchy for graph evidence and both path views. IDs stay in data. */
export function EvidenceExcerpt({ cite, quote, statement }: Props) {
  return (
    <div className="cite-card">
      {statement && <p className="evidence-statement">{statement}</p>}
      {quote && <p className="cite-quote">「{quote}」</p>}
      {!statement && !quote && <p className="cite-meta">原讲中提到这里</p>}
      <CiteLinks cite={cite} />
    </div>
  );
}
