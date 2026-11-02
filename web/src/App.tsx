import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import type { ShellContext } from "./layout/AppShell";
import { ListenDeskShell } from "./layout/ListenDeskShell";
import { GraphPage } from "./pages/GraphPage";
import { PathsPage } from "./pages/PathsPage";
import { ListenHomePage } from "./pages/listen/ListenHomePage";
import { WatchPage } from "./pages/listen/WatchPage";
import { SeriesPage } from "./pages/listen/SeriesPage";
import { SeriesDetailPage } from "./pages/listen/SeriesDetailPage";
import { SearchPage } from "./pages/listen/SearchPage";
import { StashPage } from "./pages/listen/StashPage";
import { RecallPage } from "./pages/listen/RecallPage";

export type { ShellContext };

export function App() {
  return (
    <Routes>
      {/* 学习主路径：播客听课台，无侧栏 */}
      <Route element={<ListenDeskShell />}>
        <Route path="/" element={<ListenHomePage />} />
        <Route path="/watch/:videoId" element={<WatchPage />} />
        <Route path="/series" element={<SeriesPage />} />
        <Route path="/series/:seriesId" element={<SeriesDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/stash" element={<StashPage />} />
        <Route path="/recall/:itemId" element={<RecallPage />} />
        <Route path="/lectures" element={<Navigate to="/series" replace />} />
      </Route>

      {/* 方证工具壳：保留旧侧栏，次要入口 */}
      <Route element={<AppShell />}>
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/paths" element={<PathsPage />} />
      </Route>
    </Routes>
  );
}
