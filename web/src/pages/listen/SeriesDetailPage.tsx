import { Link, useParams } from "react-router-dom";
import { formatDurationLabel, getSeries } from "../../listen/lectures";

export function SeriesDetailPage() {
  const { seriesId = "" } = useParams();
  const group = getSeries(seriesId);

  if (!group) {
    return (
      <div className="listen-stage">
        <div className="empty-card">
          <h2>没有这个系列</h2>
          <Link to="/series" className="listen-btn listen-btn-primary">
            全部系列
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="listen-stage">
      <div className="watch-nav-row">
        <Link to="/series" className="listen-text-link">
          ‹ 全部系列
        </Link>
      </div>

      <section className="series-hero-card">
        <div className="series-cover lg" aria-hidden>
          {group.label.slice(0, 1)}
        </div>
        <div>
          <h1>{group.label}</h1>
          <p>{group.blurb}</p>
          <span className="muted-sm">共 {group.count} 集 · 播客分集</span>
        </div>
      </section>

      <section className="listen-block">
        <h3 className="listen-block-title">分集节目单</h3>
        <ul className="episode-list">
          {group.lectures.map((lec, i) => (
            <li key={lec.id}>
              <Link to={`/watch/${lec.id}`} className="episode-row">
                <span className="ep-num">{String(i + 1).padStart(2, "0")}</span>
                <div className="ep-body">
                  <h3>{lec.title}</h3>
                  <span className="muted-sm">
                    {lec.id}
                    {lec.duration ? ` · ${formatDurationLabel(lec.duration)}` : ""}
                    {lec.chapters ? ` · ${lec.chapters} 章` : ""}
                  </span>
                </div>
                <span className="ep-play" aria-hidden>
                  ▶
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <div className="listen-footer-links">
        <Link to="/series">全部系列</Link>
        <Link to="/">回首页</Link>
      </div>
    </div>
  );
}
