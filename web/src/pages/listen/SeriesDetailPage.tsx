import { DeskStage } from "../../layout/DeskStage";
import { SeriesCover, seriesTitle } from "../../listen/SeriesCover";
import { watchHref } from "../../listen/citationLinks";
import { Link, useParams } from "react-router-dom";
import { formatDurationLabel, getSeries } from "../../listen/lectures";

export function SeriesDetailPage() {
  const { seriesId = "" } = useParams();
  const group = getSeries(seriesId);

  if (!group) {
    return (
      <DeskStage className="listen-series listen-episodes">
        <div className="empty-card">
          <h2>没有这个系列</h2>
          <Link to="/series" className="listen-btn listen-btn-primary">
            全部系列
          </Link>
        </div>
      </DeskStage>
    );
  }

  return (
    <DeskStage className="listen-series listen-episodes">
      <div className="watch-nav-row">
        <Link to="/series" className="listen-text-link">
          ‹ 全部系列
        </Link>
      </div>

      <section className="series-hero-card">
        <SeriesCover />
        <div>
          <h1>{seriesTitle(group)}</h1>
          <p>{group.blurb}</p>
          <span className="muted-sm">共 {group.count} 集 · 播客分集</span>
        </div>
      </section>

      <section className="listen-block">
        <h2 className="listen-block-title">分集节目单</h2>
        <ul className="episode-list">
          {group.lectures.map((lec, i) => (
            <li key={lec.id}>
              <Link to={watchHref(lec.id)!} className="episode-row">
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
    </DeskStage>
  );
}
