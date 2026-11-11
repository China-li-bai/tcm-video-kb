import { DeskStage } from "../../layout/DeskStage";
import { Link } from "react-router-dom";
import { getSeriesGroups } from "../../listen/lectures";

export function SeriesPage() {
  const groups = getSeriesGroups();

  return (
    <DeskStage>
      <div className="page-hero">
        <h1>课程系列</h1>
        <p>像播单一样挑一集听。点开就是分集节目单。</p>
      </div>

      <div className="series-cards">
        {groups.map((g, i) => (
          <Link key={g.id} to={`/series/${g.id}`} className={`series-card tone-${i % 3}`}>
            <div className="series-cover" aria-hidden>
              {g.label.slice(0, 1)}
            </div>
            <div className="series-card-body">
              <div className="series-card-head">
                <h2>{g.label}</h2>
                <span className="count-pill">{g.count} 集</span>
              </div>
              <p>{g.blurb}</p>
              <span className="series-go">看分集 ›</span>
            </div>
          </Link>
        ))}
      </div>

      <div className="listen-footer-links">
        <Link to="/">回首页听今日一小段</Link>
      </div>
    </DeskStage>
  );
}
