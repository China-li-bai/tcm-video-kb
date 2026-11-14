import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { ListenDeskShell } from "./ListenDeskShell";
import { ListenHomePage } from "../pages/listen/ListenHomePage";
import { WatchPage } from "../pages/listen/WatchPage";
import { SeriesPage } from "../pages/listen/SeriesPage";
import { SeriesDetailPage } from "../pages/listen/SeriesDetailPage";
import { SearchPage } from "../pages/listen/SearchPage";
import { StashPage } from "../pages/listen/StashPage";
import { RecallPage } from "../pages/listen/RecallPage";

const css = readFileSync(new URL("../listen.css", import.meta.url), "utf8");
// Source contract, not jsdom layout: jsdom has no viewport/flex layout engine.
// Inspect ALL matching declarations, including media rules, so a desktop row
// override cannot silently undo the mobile column contract.
function values(selector: string, property: string) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, selectors]) => selectors.split(",").some(s => s.trim() === selector))
    .flatMap(([, , body]) => body.split(";").flatMap(declaration => {
      const colon = declaration.indexOf(":");
      return declaration.slice(0, colon).trim() === property
        ? [declaration.slice(colon + 1).trim()] : [];
    }));
}
function page(path: string, route: string, element: ReactNode) {
  return renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><Routes>
    <Route element={<ListenDeskShell />}><Route path={route} element={element} /></Route>
  </Routes></MemoryRouter>);
}
it.each([
  ["/", "/", <ListenHomePage />, "narrow"],
  ["/watch/shl-001", "/watch/:videoId", <WatchPage />, "watch"],
  ["/series", "/series", <SeriesPage />, "default"],
  ["/series/shl", "/series/:seriesId", <SeriesDetailPage />, "default"],
  ["/search", "/search", <SearchPage />, "narrow"],
  ["/stash", "/stash", <StashPage />, "narrow"],
  ["/recall/unknown", "/recall/:itemId", <RecallPage />, "narrow"],
] as const)("%s uses its shared stage contract", (path, route, element, variant) => {
  expect(page(path, route, element)).toContain(`data-desk-stage="${variant}"`);
});
it.each(["GraphPage", "PathsPage"])("%s uses the full-width tool stage", name => {
  const source = readFileSync(new URL(`../pages/${name}.tsx`, import.meta.url), "utf8");
  expect(source).toMatch(/<DeskStage\s+variant="tool"/);
});
it("watch has a fixed upper slot followed by one independently scrolling script slot", () => {
  const html = page("/watch/shl-001", "/watch/:videoId", <WatchPage />);
  expect(html).toMatch(/class="watch-fixed"[\s\S]*class="script-section"[\s\S]*class="script-scroll"/);
  expect(html).toContain('data-watch-frame="stacked"');
  expect(html.match(/class="script-scroll"/g)).toHaveLength(1);
  expect(values(".listen-desk--watch .listen-stage-watch", "flex-direction")).toEqual(["column"]);
  expect(values(".watch-fixed", "width")).toEqual(["100%"]);
  expect(values(".listen-desk--watch .watch-fixed", "width")).toEqual([]);
  expect(values(".watch-fixed", "flex-shrink")).toEqual(["0"]);
});
it("watch keeps the viewport height chain locked; only script/chapters scroll", () => {
  expect(values(".listen-desk--watch", "height")).toEqual(["100vh", "100dvh"]);
  for (const selector of [".listen-desk--watch", ".listen-desk--watch .listen-main", ".listen-desk--watch .listen-stage-watch", ".listen-desk--watch .script-section"]) {
    expect(values(selector, "overflow")).toEqual(["hidden"]);
  }
  expect(values(".script-scroll", "overflow-y")).toEqual(["auto"]);
  expect(values(".watch-fixed", "overflow-y")).not.toContain("auto");
  expect(values(".listen-desk--watch .watch-fixed", "overflow-y")).not.toContain("auto");
});
it("stage widths stay variant-specific at every breakpoint and use desk tokens", () => {
  expect(values(".listen-stage", "max-width")).toEqual(["var(--desk-stage-default)"]);
  expect(values(".listen-stage-narrow", "max-width")).toEqual(["var(--desk-stage-narrow)"]);
  expect(values(".listen-stage-watch", "max-width")).toEqual(["var(--desk-stage-watch)"]);
  expect(values(".listen-desk--watch .listen-stage-watch", "max-width")).toEqual([]);
  expect(values(".listen-stage-tool", "max-width")).toEqual(["none"]);
});
it("desktop search has a readable minimum width; desktop has no floating bottom nav", () => {
  expect(values(".listen-search", "min-width")).toContain("0");
  expect(values(".listen-search", "min-width")).toContain("20rem");
  expect(values(".listen-mob-nav", "display")).toContain("none !important");
  expect(values(".listen-desk--watch .listen-mob-nav", "position")).toEqual(["relative"]);
});

it("shared reading and action typography consume desk scale tokens", () => {
  expect(values(".utter-body p", "font-size")).toEqual(["var(--desk-text-reading)"]);
  expect(values(".utter-body p", "line-height")).toEqual(["var(--desk-leading-reading)"]);
  expect(values(".listen-btn-lg", "font-size")).toEqual(["var(--desk-text-reading)"]);
});
