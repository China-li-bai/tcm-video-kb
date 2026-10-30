import { Link } from "react-router-dom";
import { DEFAULT_FOCUS } from "../types";

const ENTRIES = [
  {
    to: `/graph?focus=${encodeURIComponent(DEFAULT_FOCUS)}`,
    title: "方证关系图",
    desc: "以焦点实体展开组成、主治与提示关系，点边可核对出处。",
  },
  {
    to: `/paths?focus=${encodeURIComponent("syndrome.tai_yang_bing")}`,
    title: "路径分轨",
    desc: "同权并列多条证型路径，不做排行，也不标唯一证型。",
  },
  {
    to: "/lectures",
    title: "讲次",
    desc: "浏览仓库内已入库讲次目录，可按系列与标题检索。",
  },
] as const;

const QUICK = [
  { label: "桂枝汤", focus: "formula.gui_zhi_tang", path: "/graph" },
  { label: "太阳病", focus: "syndrome.tai_yang_bing", path: "/paths" },
] as const;

export function HomePage() {
  return (
    <div className="home">
      <section className="home-hero">
        <p className="eyebrow">人纪 · 方证图</p>
        <h2 className="home-title">学用分界清楚的方证关系中台</h2>
        <p className="home-lead">
          本站用于学习倪师讲授中的方证结构与出处核对，不是诊疗工具。讲课边均为
          candidate，不进入检索主文案；多证同权，不标唯一证型。
        </p>
      </section>

      <section className="entry-grid" aria-label="主要入口">
        {ENTRIES.map((item) => (
          <Link key={item.title} to={item.to} className="entry-card">
            <h3>{item.title}</h3>
            <p>{item.desc}</p>
            <span className="entry-link">进入</span>
          </Link>
        ))}
      </section>

      <section className="quick-open" aria-label="快开">
        <h3 className="section-label">快开</h3>
        <div className="quick-row">
          {QUICK.map((item) => (
            <Link
              key={item.label}
              className="btn btn-secondary"
              to={`${item.path}?focus=${encodeURIComponent(item.focus)}`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
