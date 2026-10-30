import { FormEvent, useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, Route, Routes, useSearchParams } from "react-router-dom";
import { GraphPage } from "./pages/GraphPage";
import { PathsPage } from "./pages/PathsPage";
import { DEFAULT_FOCUS } from "./types";

export type ShellContext = { focus: string };

function Shell() {
  const [params, setParams] = useSearchParams();
  const focus = params.get("focus") || DEFAULT_FOCUS;
  const [draft, setDraft] = useState(focus);

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

  return (
    <>
      <header className="top">
        <div>
          <h1>伤寒方证子图</h1>
          <p className="disclaimer">
            学习倪师讲授，非诊疗建议。讲课边都是 candidate，不进检索。多证同权，不标唯一证型。
          </p>
        </div>
        <nav>
          <NavLink to={`/graph?focus=${encodeURIComponent(focus)}`}>关系图</NavLink>
          <NavLink to={`/paths?focus=${encodeURIComponent(focus)}`}>路径分轨</NavLink>
        </nav>
        <form onSubmit={onSubmit}>
          <label>
            焦点
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              spellCheck={false}
            />
          </label>
          <button type="submit">打开</button>
        </form>
      </header>
      <Outlet context={{ focus } satisfies ShellContext} />
    </>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<Navigate to={`/graph?focus=${DEFAULT_FOCUS}`} replace />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/paths" element={<PathsPage />} />
      </Route>
    </Routes>
  );
}
