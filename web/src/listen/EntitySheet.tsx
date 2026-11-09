import { watchHref } from "./citationLinks";
import { Link } from "react-router-dom";
import {
  entityTypeBadge,
  isGraphableEntity,
  type EntityMention,
} from "./entities";
import { formatClock } from "./lectures";

type Props = {
  open: boolean;
  mention: EntityMention | null;
  /** Current watch video — for 「回听」 deep link when opening graph. */
  videoId: string;
  /** Current sentence time — kept in URL so back/回听 lands on same t. */
  t: number;
  onClose: () => void;
  onListen: () => void;
};

/**
 * Mini 对照 for a transcript entity chip.
 * Stay in listen shell by default; graph is optional旁证.
 */
export function EntitySheet({
  open,
  mention,
  videoId,
  t,
  onClose,
  onListen,
}: Props) {
  if (!open || !mention) return null;

  const badge = entityTypeBadge(mention.type);
  const graphable = isGraphableEntity(mention);
  const watchBack = watchHref(videoId, t);
  const graphHref = `/graph?focus=${encodeURIComponent(mention.entity_id)}`;

  return (
    <div
      className="entity-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="entity-sheet-title"
    >
      <button
        type="button"
        className="entity-backdrop"
        aria-label="关闭"
        onClick={onClose}
      />
      <div className="entity-sheet">
        <div className="entity-sheet-head">
          <h2 id="entity-sheet-title">对照一下</h2>
          <button
            type="button"
            className="entity-close"
            onClick={onClose}
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        <div className="entity-sheet-body">
          <div className="entity-hero">
            <span className="entity-badge">{badge}</span>
            <span className="entity-name">{mention.label}</span>
          </div>
          <p className="entity-meta">
            原讲约 {formatClock(mention.start_s)}
            {mention.end_s > mention.start_s
              ? `–${formatClock(mention.end_s)}`
              : ""}{" "}
            提到
          </p>
          <p className="entity-plain">
            先听原讲里怎么说。关系图是旁证，不是这一课的主场。
          </p>

          <div className="entity-actions">
            <button
              type="button"
              className="listen-btn listen-btn-primary"
              onClick={onListen}
            >
              继续听
            </button>
            {graphable ? (
              <Link
                to={graphHref}
                className="listen-btn listen-btn-ghost"
                onClick={onClose}
              >
                看关系图
              </Link>
            ) : (
              <span className="entity-no-graph">图上暂未挂这条</span>
            )}
            <button type="button" className="listen-text-link" onClick={onClose}>
              关了
            </button>
          </div>

          {graphable && watchBack && (
            <p className="entity-back-hint">
              从图里回来：浏览器后退，或打开{" "}
              <Link to={watchBack} className="listen-text-link" onClick={onClose}>
                回听原处
              </Link>
            </p>
          )}
        </div>

        <div className="entity-sheet-foot">听是主场 · 图是旁证 · 非诊疗</div>
      </div>
    </div>
  );
}
