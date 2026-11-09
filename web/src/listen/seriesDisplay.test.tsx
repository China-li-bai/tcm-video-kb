// @vitest-environment jsdom
// Only external I/O is replaced. Real pages, routers, search, storage and display readers run.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import raw from '../data/lectures.json';
import { getAllLectures, getLecture, getSeries, searchLectures } from './lectures';
import { searchCatalog } from './search';
import { LAST_KEY, STASH_KEY } from './stash';
import { SeriesPage } from '../pages/listen/SeriesPage';
import { SeriesDetailPage } from '../pages/listen/SeriesDetailPage';
import { WatchPage } from '../pages/listen/WatchPage';
import { ListenHomePage } from '../pages/listen/ListenHomePage';
import { SearchPage } from '../pages/listen/SearchPage';
import { StashPage } from '../pages/listen/StashPage';
import { RecallPage } from '../pages/listen/RecallPage';
import { LecturesPage } from '../pages/LecturesPage';

const sourceRows = raw.lectures.filter(l => l.series === 'nj');
const source = sourceRows[0];
const snapshot = JSON.stringify(raw);
const label = '黄帝内经';
const blurb = '黄帝内经：按原讲次标题，逐集听原讲。';

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    if (!/^\/(transcripts|knowledge|entities)\/[a-z]+-\d{3}\.json$/.test(String(input))) throw new Error(`No network fallback: ${input}`);
    return new Response('fixture unavailable', { status: 404 });
  }));
  Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() });
  vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); expect(JSON.stringify(raw)).toBe(snapshot); });

function Location() { const l = useLocation(); return <output data-testid="location">{l.pathname}{l.search}</output>; }
function open(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Location/><Routes>
    <Route path="/" element={<ListenHomePage/>}/><Route path="/series" element={<SeriesPage/>}/>
    <Route path="/series/:seriesId" element={<SeriesDetailPage/>}/><Route path="/watch/:videoId" element={<WatchPage/>}/>
    <Route path="/search" element={<SearchPage/>}/><Route path="/lectures" element={<LecturesPage/>}/>
    <Route path="/stash" element={<StashPage/>}/><Route path="/recall/:itemId" element={<RecallPage/>}/>
  </Routes></MemoryRouter>);
}
function route() { return screen.getByTestId('location').textContent; }

it('projects exactly the ten source-backed display labels without migrating any original source field or identity', () => {
  expect(sourceRows).toHaveLength(10);
  for (const row of raw.lectures) {
    expect(getLecture(row.id)).toEqual({ ...row, seriesLabel: row.series === 'nj' ? label : row.seriesLabel });
  }
  expect(getAllLectures().map(l => l.id)).toEqual(raw.lectures.map(l => l.id));
  expect(sourceRows.every(l => l.title.includes('《黄帝内经》') && l.seriesLabel === '难经')).toBe(true);
});
it('series grouping and plain-language blurb agree without guessing extra teaching content', () => {
  const group = getSeries('nj')!;
  expect(group.label).toBe(label); expect(group.blurb).toBe(blurb); expect(group.count).toBe(10);
  expect(group.lectures.map(l => l.id)).toEqual(sourceRows.map(l => l.id));
});
it('canonical name, source titles and legacy stable IDs remain searchable; the erroneous label is not endorsed as a series alias', () => {
  expect(searchLectures(label).map(l => l.id)).toEqual(sourceRows.map(l => l.id));
  expect(searchLectures(source.title).map(l => l.id)).toContain(source.id);
  expect(searchLectures('nj-010').map(l => l.id)).toEqual(['nj-010']);
  expect(searchLectures('难经').filter(l => l.series === 'nj')).toEqual([]);
  const hits = searchCatalog('nj-001');
  expect(hits.some(h => h.href === '/watch/nj-001' && h.lecture.seriesLabel === label)).toBe(true);
  expect(searchCatalog('难经').filter(h => h.kind === 'lecture' && h.lecture.series === 'nj')).toEqual([]);
});
it('series list -> ten-episode detail -> original Watch ID -> breadcrumb remains the same series', async () => {
  open('/series');
  fireEvent.click(screen.getByRole('heading', { name: label }).closest('a')!);
  expect(route()).toBe('/series/nj'); expect(screen.getByRole('heading', { level: 1, name: label })).toBeTruthy();
  expect(document.querySelectorAll('.episode-row')).toHaveLength(10);
  expect(screen.getByText(blurb)).toBeTruthy();
  fireEvent.click(screen.getByRole('heading', { name: source.title }).closest('a')!);
  expect(route()).toBe('/watch/nj-001');
  expect(await screen.findByText('这集还没有对齐好的文稿。')).toBeTruthy();
  const crumb = document.querySelector('.series-chip')!;
  expect(crumb.textContent).toBe('黄帝内经 · nj-001');
  fireEvent.click(crumb); expect(route()).toBe('/series/nj');
  expect(vi.mocked(fetch).mock.calls.some(([url]) => /^\/transcripts\/nj-/.test(String(url)))).toBe(false); // nj coverage was not invented by relabelling.
});
it('the legacy catalog filter/list shares the display reader but keeps original source titles and YouTube URLs', () => {
  open('/lectures');
  expect(screen.getByRole('option', { name: '黄帝内经（nj）' })).toBeTruthy();
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'nj' } });
  const rows = document.querySelectorAll('.lecture-row'); expect(rows).toHaveLength(10);
  rows.forEach((row, i) => {
    expect(row.querySelector('.pill')!.textContent).toBe(label);
    expect(row.querySelector('h3')!.textContent).toBe(sourceRows[i].title);
    expect(row.querySelector('a')!.getAttribute('href')).toBe(`https://www.youtube.com/watch?v=${sourceRows[i].youtubeId}`);
  });
});
it('actual search submission renders canonical hit metadata and navigates with the unchanged nj identity', async () => {
  open('/search');
  const input = screen.getByRole('textbox'); fireEvent.change(input, { target: { value: label } });
  fireEvent.submit(input.closest('form')!);
  await waitFor(() => expect(screen.queryByText('正在翻原文句子…')).toBeNull());
  const card = screen.getByRole('heading', { name: source.title }).closest('article')!;
  expect(within(card).getByText(/^黄帝内经 · 约/)).toBeTruthy();
  expect(within(card).getByText('黄帝内经 · nj-001')).toBeTruthy();
  expect(within(card).getByRole('link', { name: '看系列' }).getAttribute('href')).toBe('/series/nj');
  fireEvent.click(within(card).getByRole('link', { name: '听原讲' }));
  expect(route()).toBe('/watch/nj-001'); expect(document.querySelector('.series-chip')!.textContent).toBe('黄帝内经 · nj-001');
});
it('homepage resumes an old nj request without renaming stored source titles or treating it as playback', () => {
  const saved = JSON.stringify({ videoId: source.id, title: source.title, t: 12.75, updatedAt: '2026-11-09T00:00:00Z' });
  localStorage.setItem(LAST_KEY, saved); open('/');
  const resume = document.querySelector('.resume-bar')!;
  expect(resume.textContent).toContain(source.title); expect(resume.getAttribute('href')).toBe('/watch/nj-001?t=12');
  expect(localStorage.getItem(LAST_KEY)).toBe(saved);
  expect(screen.getByText('这里只记打开或点选的位置，不是播放进度。')).toBeTruthy();
  fireEvent.click(resume); expect(route()).toBe('/watch/nj-001?t=12');
  expect(document.querySelector('.series-chip')!.textContent).toBe('黄帝内经 · nj-001');
});
it('historical stash -> recall -> source keeps personal legacy wording/IDs/bytes while displaying the corrected series', () => {
  const saved = JSON.stringify([{ id: 'old-nj-note', videoId: source.id, title: '旧收藏题名：难经（本人备注）', text: '合成收藏原句', t: 0.75, savedAt: '2026-11-09T00:00:00Z' }]);
  localStorage.setItem(STASH_KEY, saved); open('/stash');
  expect(document.querySelector('.stash-where')!.textContent).toContain('黄帝内经 · nj-001');
  fireEvent.click(screen.getByRole('link', { name: '先回想' }));
  expect(route()).toBe('/recall/old-nj-note');
  expect(screen.getByText(/出处：黄帝内经 · nj-001 · 旧收藏题名：难经/)).toBeTruthy();
  expect(localStorage.getItem(STASH_KEY)).toBe(saved);
  fireEvent.click(screen.getByRole('link', { name: '听原讲' }));
  expect(route()).toBe('/watch/nj-001'); expect(document.querySelector('.series-chip')!.textContent).toBe('黄帝内经 · nj-001');
  expect(localStorage.getItem(STASH_KEY)).toBe(saved);
});
