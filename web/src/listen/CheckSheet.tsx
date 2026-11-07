import { useEffect, useState } from "react";
import {
  type KnowledgePoint,
  typeLabel,
} from "./knowledgePoints";
import { formatClock } from "./lectures";

type Props = {
  open: boolean;
  quote: string;
  where: string;
  /** Current sentence time (seconds) — used only for labels / seek. */
  t: number;
  /** Nearby claims already picked by WatchPage; empty = honest empty state. */
  claims: KnowledgePoint[];
  /** True while KP JSON is still loading for this video. */
  claimsLoading?: boolean;
  onClose: () => void;
  onListen: () => void;
  onStash: () => void;
  /** Optional: jump to a claim's start when user taps「听这段主张」. */
  onListenClaim?: (claim: KnowledgePoint) => void;
};

/**
 * 「问这句」= 对照原讲主张，不是考分。
 * Options come from exported knowledge points near video_id+t; never invent MCQ.
 */
export function CheckSheet({
  open,
  quote,
  where,
  t,
  claims,
  claimsLoading = false,
  onClose,
  onListen,
  onStash,
  onListenClaim,
}: Props) {
  const [pickedId, setPickedId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) setPickedId(null);
  }, [open, claims]);

  if (!open) return null;

  const picked = claims.find((c) => c.kp_id === pickedId) ?? null;
  const empty = !claimsLoading && claims.length === 0;

  return (
    <div className="check-overlay" role="dialog" aria-modal="true" aria-labelledby="check-title">
      <button type="button" className="check-backdrop" aria-label="关闭" onClick={onClose} />
      <div className="check-sheet">
        <div className="check-sheet-head">
          <h2 id="check-title">对照原讲主张</h2>
          <button type="button" className="check-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>

        <div className="check-sheet-body">
          <div>
            <p className="check-label">刚才这句</p>
            <div className="check-quote">{quote}</div>
          </div>

          {claimsLoading && (
            <p className="check-hint">正在找这段附近有没有核对过的主张…</p>
          )}

          {!claimsLoading && claims.length > 0 && (
            <div className="check-options" role="list">
              <p className="check-hint">
                这段附近，原讲里已经核对过的主张（不评分，只帮你对照）：
              </p>
              {claims.map((claim) => {
                const active = pickedId === claim.kp_id;
                return (
                  <button
                    key={claim.kp_id}
                    type="button"
                    className={active ? "check-option check-option-active" : "check-option"}
                    role="listitem"
                    aria-pressed={active}
                    onClick={() => setPickedId(claim.kp_id)}
                  >
                    <span className="check-option-meta">
                      <span className="check-option-type">{typeLabel(claim.type)}</span>
                      <span className="check-option-time">
                        {formatClock(claim.start_s)}
                        {claim.end_s > claim.start_s ? `–${formatClock(claim.end_s)}` : ""}
                      </span>
                    </span>
                    <span className="check-option-text">{claim.statement}</span>
                  </button>
                );
              })}
            </div>
          )}

          {empty && (
            <div className="check-empty" role="status">
              <p className="check-empty-title">这段还没核对过主张</p>
              <p className="check-empty-body">
                约 {formatClock(t)} 附近暂时没有可对照的知识点。先听原讲、或收下这句；等核对过再回来问。
              </p>
            </div>
          )}

          {picked && (
            <div className="check-picked">
              <p className="check-label">白话对照</p>
              <p className="check-plain">
                以倪老师原讲为准。上面这条是从本集核对过的知识点里挑出来的主张，不是考题答案。
                不确定就回到原句再听一遍。
              </p>
              {picked.evidence_quote ? (
                <p className="check-evidence">
                  <span className="check-label">原讲里相近的话</span>
                  「{picked.evidence_quote}」
                </p>
              ) : null}
              {onListenClaim && (
                <button
                  type="button"
                  className="listen-text-link"
                  onClick={() => onListenClaim(picked)}
                >
                  听这段主张的开头
                </button>
              )}
            </div>
          )}

          {!picked && !empty && !claimsLoading && (
            <p className="check-plain">
              先点一条主张对照一下。听原讲会回到学一段对应位置。不确定就再听一遍原句。
            </p>
          )}

          <p className="check-where">{where}</p>

          <div className="check-actions">
            <button type="button" className="listen-btn listen-btn-primary" onClick={onListen}>
              听原讲
            </button>
            <button type="button" className="listen-btn listen-btn-ghost" onClick={onStash}>
              收下
            </button>
            <button type="button" className="listen-text-link" onClick={onClose}>
              关了继续听
            </button>
          </div>
        </div>

        <div className="check-sheet-foot">以原讲为准 · 学习用，非诊疗</div>
      </div>
    </div>
  );
}
