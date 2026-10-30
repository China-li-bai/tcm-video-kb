import { FormEvent, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { DEFAULT_FOCUS } from "../types";

export type ShellContext = { focus: string };

const NAV = [
  { to: "/", label: "首页", end: true },
  { to: "/graph", label: "关系图", end: false },
  { to: "/paths", label: "路径", end: false },
  { to: "/lectures", label: "讲次", end: false },
] as const;

const PAGE_TITLE: Record<string, string> = {
  "/": "首页",
  "/graph": "方证关系图",
  "/paths": "路径分轨",
  "/lectures": "讲次浏览",
};

export function AppShell() {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const focus = params.get("focus") || DEFAULT_FOCUS;
  const [draft, setDraft] = useState(focus);
  const showFocus = location.pathname === "/graph" || location.pathname === "/paths";
  const title = PAGE_TITLE[location.pathname] ?? "人纪";

  useEffect(() => {
    setDraft(focus);
  }, [focus]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const next = draft.trim();
    if (!next) return;
    const query = new URLSearchParams(params);
    query.set("focus", next);
    setParams(query);
  }

  function navTo(path: string) {
    if (path === "/graph" || path === "/paths") {
      return `${path}?focus=${encodeURIComponent(focus)}`;
    }
    return path;
  }

  return (
    <div className="app">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <div className="brand-text">
            <strong>人纪</strong>
            <span>方证图</span>
          </div>
        </div>
        <nav className="side-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={navTo(item.to)}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="app-body">
        <header className="topbar">
          <div className="topbar-left">
            <h1 className="page-title">{title}</h1>
            <p className="disclaimer">学习用 · 非诊疗 · 讲课边不进检索</p>
          </div>
          {showFocus && (
            <form className="focus-form" onSubmit={onSubmit}>
              <label className="focus-label">
                <span>焦点</span>
                <input
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  spellCheck={false}
                  placeholder="formula.gui_zhi_tang"
                />
              </label>
              <button type="submit" className="btn btn-primary">
                打开
              </button>
            </form>
          )}
        </header>
        <div className="content">
          <Outlet context={{ focus } satisfies ShellContext} />
        </div>
      </div>
    </div>
  );
}
