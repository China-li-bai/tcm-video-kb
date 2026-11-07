import { Navigate, Route, Routes } from "react-router-dom";
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

/**
 * Single learner shell: ListenDeskShell for home/watch/series/stash
 * and for secondary /graph + /paths (no AppShell sidebar fork).
 */
export function App() {
  return (
    <Routes>
      <Route element={<ListenDeskShell />}>
        <Route path="/" element={<ListenHomePage />} />
        <Route path="/watch/:videoId" element={<WatchPage />} />
        <Route path="/series" element={<SeriesPage />} />
        <Route path="/series/:seriesId" element={<SeriesDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/stash" element={<StashPage />} />
        <Route path="/recall/:itemId" element={<RecallPage />} />
        <Route path="/lectures" element={<Navigate to="/series" replace />} />
        {/* 旁证工具：同壳，无中台侧栏 */}
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/paths" element={<PathsPage />} />
      </Route>
    </Routes>
  );
}
