import { useMemo, useState } from "react";
import { getAllLectures } from "../listen/lectures";

const lectures = getAllLectures();

export function LecturesPage() {
  const [q, setQ] = useState("");
  const [series, setSeries] = useState("all");

  const seriesOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of lectures) {
      if (item.series) map.set(item.series, item.seriesLabel || item.series);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return lectures.filter((item) => {
      if (series !== "all" && item.series !== series) return false;
      if (!needle) return true;
      return (
        item.id.toLowerCase().includes(needle) ||
        item.title.toLowerCase().includes(needle) ||
        item.seriesLabel.toLowerCase().includes(needle)
      );
    });
  }, [q, series]);

  if (lectures.length === 0) {
    return (
      <div className="page-pad">
        <div className="empty-state">
          <h2>讲次数据接入中</h2>
          <p className="muted">
            当前前端未读到讲次索引。仓库内讲次在 <code>data/knowledge</code>，接入后将在此展示可搜列表。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-pad lectures">
      <div className="lectures-toolbar">
        <label className="search-field">
          <span className="sr-only">搜索讲次</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索讲次 id 或标题"
            spellCheck={false}
          />
        </label>
        <label className="filter-field">
          <span>系列</span>
          <select value={series} onChange={(e) => setSeries(e.target.value)}>
            <option value="all">全部</option>
            {seriesOptions.map(([key, label]) => (
              <option key={key} value={key}>
                {label}（{key}）
              </option>
            ))}
          </select>
        </label>
        <p className="muted count">{filtered.length} / {lectures.length}</p>
      </div>

      <ul className="lecture-list">
        {filtered.map((item) => (
          <li key={item.id} className="lecture-row">
            <div>
              <div className="lecture-meta">
                <span className="pill">{item.seriesLabel}</span>
                <code className="mono">{item.id}</code>
                {item.chapters > 0 && <span className="muted">{item.chapters} 章</span>}
                {item.duration && <span className="muted">{item.duration}</span>}
              </div>
              <h3 className="lecture-title">{item.title}</h3>
            </div>
            {item.youtubeId ? (
              <a
                className="btn btn-secondary"
                href={`https://www.youtube.com/watch?v=${item.youtubeId}`}
                target="_blank"
                rel="noreferrer"
              >
                出处
              </a>
            ) : (
              <span className="muted">无链接</span>
            )}
          </li>
        ))}
      </ul>

      {filtered.length === 0 && (
        <p className="empty">没有匹配的讲次。试试换系列或清空搜索。</p>
      )}
    </div>
  );
}
