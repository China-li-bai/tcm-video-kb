type Props = {
  open: boolean;
  quote: string;
  where: string;
  onClose: () => void;
  onListen: () => void;
  onStash: () => void;
};

const FAKE_OPTIONS = [
  "服后最好只见一层薄薄的、似有若无的汗——说明营卫通了、邪有出路。",
  "要大汗淋漓才算药力到位，汗得越多越好。",
  "这句主要在讲药味多少，跟出汗没关系。",
];

export function CheckSheet({ open, quote, where, onClose, onListen, onStash }: Props) {
  if (!open) return null;

  return (
    <div className="check-overlay" role="dialog" aria-modal="true" aria-labelledby="check-title">
      <button type="button" className="check-backdrop" aria-label="关闭" onClick={onClose} />
      <div className="check-sheet">
        <div className="check-sheet-head">
          <h2 id="check-title">这句大概在说什么</h2>
          <button type="button" className="check-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>

        <div className="check-sheet-body">
          <div>
            <p className="check-label">刚才这句</p>
            <div className="check-quote">{quote}</div>
          </div>

          <div className="check-options" role="list">
            <p className="check-hint">先自己挑一个说法（不评分，只帮你想清楚）：</p>
            {FAKE_OPTIONS.map((opt) => (
              <button key={opt} type="button" className="check-option" role="listitem">
                {opt}
              </button>
            ))}
          </div>

          <p className="check-plain">
            白话说：以倪老师原讲为准。听原讲会回到学一段对应位置。不确定就再听一遍原句。
          </p>
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
