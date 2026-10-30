import { Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import type { ShellContext } from "./layout/AppShell";
import { GraphPage } from "./pages/GraphPage";
import { HomePage } from "./pages/HomePage";
import { LecturesPage } from "./pages/LecturesPage";
import { PathsPage } from "./pages/PathsPage";

export type { ShellContext };

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/paths" element={<PathsPage />} />
        <Route path="/lectures" element={<LecturesPage />} />
      </Route>
    </Routes>
  );
}
