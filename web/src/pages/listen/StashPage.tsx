import { watchHref } from "../../listen/citationLinks";
import { useState } from "react";
import { Link } from "react-router-dom";
import { formatClock, getLecture } from "../../listen/lectures";
import { listStash, removeStashItem } from "../../listen/stash";

export function StashPage() {
  const [items, setItems] = useState(() => listStash());

  function refresh() {
    setItems(listStash());
  }

  return (
    <div className="listen-stage listen-stage-narrow">
      <div className="page-hero row">
        <span className="stash-entry-ico lg" aria-hidden>
          ▣
        </span>
        <div>
          <h1>收获匣</h1>
          <p>你收下的几句。过几天先回想；忘了就听原讲。</p>
        </div>
      </div>

      {items.length === 0 && (
        <div className="empty-card">
          <h2>匣子还是空的</h2>
          <p>听的时候点「收下」，句子会落在这里。过几天回来先回想。</p>
          <Link to="/" className="listen-btn listen-btn-primary">
            去听今日一小段
          </Link>
        </div>
      )}

      <ul className="stash-list">
        {items.map((item) => {
          const lec = getLecture(item.videoId);
          const replayHref = watchHref(item.videoId, item.t);
          const where = lec
            ? `${lec.seriesLabel} · ${item.videoId}${item.t != null ? ` · 约 ${formatClock(item.t)}` : ""}`
            : item.videoId;
          return (
            <li key={item.id}>
              <article className="stash-card">
                <p className="stash-quote">{item.text}</p>
                <p className="muted-sm stash-where">
                  {where}
                  {item.title ? ` · ${item.title}` : ""}
                </p>
                <div className="hit-actions">
                  <Link to={`/recall/${item.id}`} className="listen-btn listen-btn-primary">
                    先回想
                  </Link>
                  {replayHref ? <Link to={replayHref} className="listen-btn listen-btn-ghost">
                    听原讲
                  </Link> : <span className="muted-sm">出处信息不完整，暂不能定位原讲。</span>}
                  <button
                    type="button"
                    className="listen-text-link"
                    onClick={() => {
                      removeStashItem(item.id);
                      refresh();
                    }}
                  >
                    拿掉
                  </button>
                </div>
              </article>
            </li>
          );
        })}
      </ul>

      <div className="listen-footer-links">
        <Link to="/">回首页</Link>
      </div>
    </div>
  );
}
