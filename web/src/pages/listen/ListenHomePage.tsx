import { useMemo } from "react";
import { Link } from "react-router-dom";
import { enrichTodayFromChapters } from "../../listen/chapters";
import { getAllLectures, pickTodaySegment } from "../../listen/lectures";
import { requestedSeconds } from "../../listen/staticPlayback";
import { getLastWatch, listStash } from "../../listen/stash";

export function ListenHomePage() {
  const today = useMemo(() => {
    const base = pickTodaySegment();
    const enriched = enrichTodayFromChapters(base.lecture.id);
    if (!enriched) return base;
    return {
      lecture: base.lecture,
      chapterTitle: enriched.chapterTitle,
      chapterId: enriched.chapterId,
      approxMin: Math.min(20, Math.max(8, enriched.approxMin)),
      topics: enriched.topics,
      startS: enriched.startS,
    };
  }, []);

  const last = getLastWatch();
  const stashCount = listStash().length;
  const upNext = useMemo(() => {
    const all = getAllLectures().filter((l) => l.series === today.lecture.series && l.id !== today.lecture.id);
    return all.slice(0, 2);
  }, [today.lecture.id, today.lecture.series]);

  const watchTo = `/watch/${today.lecture.id}${today.startS ? `?t=${Math.floor(today.startS)}` : ""}`;

  return (
    <div className="listen-stage listen-stage-narrow">
      <section className="today-card">
        <div className="today-wash" aria-hidden />
        <span className="today-chip">今日一小段 · 约 {today.approxMin} 分钟</span>
        <h1 className="today-title">{today.chapterTitle}</h1>
        <div className="today-topics">
          <span className="today-topics-label">这段会讲到：</span>
          {today.topics.map((t) => (
            <span key={t} className="topic-pill">
              {t}
            </span>
          ))}
        </div>
        <Link to={watchTo} className="listen-btn listen-btn-primary listen-btn-lg">
          开始听
        </Link>
        <p className="today-meta">
          {today.lecture.seriesLabel} · {today.lecture.id}
        </p>
      </section>

      {last && (
        <section className="listen-block">
          <h3 className="listen-block-title">接着听</h3>
          <Link to={`/watch/${last.videoId}${last.t ? `?t=${requestedSeconds(last.t)}` : ""}`} className="resume-bar">
            <div className="resume-ico" aria-hidden>
              ↻
            </div>
            <div className="resume-text">
              <span className="resume-sub">上次打开的位置</span>
              <span className="resume-main">{last.chapterTitle || last.title}</span>
            </div>
            <span className="resume-play" aria-hidden>
              ▶
            </span>
          </Link>
          <p className="muted-sm">这里只记打开或点选的位置，不是播放进度。</p>
        </section>
      )}

      {upNext.length > 0 && (
        <section className="listen-block">
          <h3 className="listen-block-title">也可以选一集</h3>
          <ul className="upnext-list">
            {upNext.map((lec) => (
              <li key={lec.id}>
                <Link to={`/watch/${lec.id}`} className="upnext-row">
                  <div>
                    <h4>{lec.title.replace(/^倪海廈[^：:]*[：:]?\s*/u, "").slice(0, 28) || lec.title}</h4>
                    <span className="muted-sm">
                      {lec.seriesLabel} · {lec.duration || lec.id}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Link to="/stash" className="stash-entry">
        <div className="stash-entry-left">
          <span className="stash-entry-ico" aria-hidden>
            ▣
          </span>
          <div>
            <strong>收获匣</strong>
            <p>
              {stashCount > 0
                ? `${stashCount} 句存货 · 先回想，忘了就听原讲`
                : "还空着 · 听的时候可以收下几句"}
            </p>
          </div>
        </div>
        <span aria-hidden>›</span>
      </Link>

      <div className="listen-footer-links">
        <Link to="/series">全部课程系列</Link>
        <Link to="/graph?focus=formula.gui_zhi_tang">方证图</Link>
        <Link to="/paths?focus=syndrome.tai_yang_bing">路径</Link>
      </div>
    </div>
  );
}

