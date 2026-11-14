import { DeskStage } from "../../layout/DeskStage";
import { watchHref } from "../../listen/citationLinks";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getLecture } from "../../listen/lectures";
import { getStashItem, saveStashItem } from "../../listen/stash";

export function RecallPage() {
  const { itemId = "" } = useParams();
  const item = getStashItem(itemId);
  const [revealed, setRevealed] = useState(false);
  const [toast, setToast] = useState("");

  if (!item) {
    return (
      <DeskStage variant="narrow" className="listen-recall">
        <section className="empty-card desk-state-card">
          <h2>找不到这句存货</h2>
          <p>可能已经拿掉了。回收获匣看看。</p>
          <Link to="/stash" className="listen-btn listen-btn-primary">
            回收获匣
          </Link>
        </section>
      </DeskStage>
    );
  }

  const replayHref = watchHref(item.videoId, item.t);
  const lec = getLecture(item.videoId);
  const where = lec
    ? `${lec.seriesLabel} · ${item.videoId}${item.title ? ` · ${item.title}` : ""}`
    : item.title;

  return (
    <DeskStage variant="narrow" className="listen-recall">
      <div className="watch-nav-row">
        <Link to="/stash" className="listen-text-link">
          回收获匣
        </Link>
      </div>

      <div className="recall-hero">
        <span className="muted-sm">先自己想一想</span>
        <h1>这句大概讲什么？</h1>
        <p className="muted-sm">出处：{where}</p>
      </div>

      <section className={`recall-card${revealed ? " reveal" : ""}`}>
        <p className="blur-line recall-quote">{item.text}</p>
        <p className="muted-sm">原句先遮着。想不起来就听原讲；想起来了可以再收下。</p>
        <div className="hit-actions center">
          {replayHref ? <Link to={replayHref} className="listen-btn listen-btn-primary">
            听原讲
          </Link> : <span className="muted-sm">出处信息不完整，暂不能定位原讲。</span>}
          <button
            type="button"
            className="listen-btn listen-btn-ghost"
            onClick={() => setRevealed(true)}
          >
            先看一眼原句
          </button>
        </div>
      </section>

      <div className="hit-actions center recall-secondary-actions">
        <button
          type="button"
          className="listen-btn listen-btn-ghost"
          onClick={() => {
            saveStashItem({
              videoId: item.videoId,
              title: item.title,
              text: item.text,
              t: item.t,
            });
            setToast("又收下了");
            window.setTimeout(() => setToast(""), 1600);
          }}
        >
          再收下
        </button>
        <Link to="/stash" className="listen-text-link">
          回收获匣
        </Link>
      </div>

      {toast && <div className="listen-toast">{toast}</div>}
    </DeskStage>
  );
}
