// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { loadTranscript, type TranscriptFile } from './transcript';
import { WatchPage } from '../pages/listen/WatchPage';
vi.mock('./transcript', () => ({ loadTranscript: vi.fn() }));
vi.mock('./knowledgePoints', () => ({ loadKnowledgePoints: async () => null, pickClaimsNear: () => [] }));
vi.mock('./entities', () => ({ loadEntities: async () => null, pickChipsNear: () => [], entityTypeBadge: () => '' }));
const file: TranscriptFile = { video_id: 'shl-001', segments: [
  { seq: 0, start_s: 12, end_s: 30, text: '已到达的句稿' },
] };
function pending() {
  let resolve!: (file: TranscriptFile | null) => void;
  const promise = new Promise<TranscriptFile | null>(done => { resolve = done; });
  return { promise, resolve };
}
function open() {
  return render(<MemoryRouter initialEntries={['/watch/shl-001?t=12']}>
    <Link to="/watch/jgy-001">切换讲次</Link>
    <Routes><Route path="/watch/:videoId" element={<WatchPage />} /></Routes>
  </MemoryRouter>);
}
beforeEach(() => {
  vi.mocked(loadTranscript).mockReset();
  localStorage.clear();
  Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() });
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('announces loading only while waiting, then replaces it with sentences', async () => {
  const job = pending();
  vi.mocked(loadTranscript).mockReturnValue(job.promise);
  open();
  expect(screen.getByRole('status', { name: '转写加载状态' }).textContent).toBe('文稿加载中…');
  await act(async () => job.resolve(file));
  expect(screen.getByText('已到达的句稿')).toBeTruthy();
  expect(screen.queryByText('文稿加载中…')).toBeNull();
});
it('settled unavailable data never leaves loading alongside chapter summaries', async () => {
  const job = pending();
  vi.mocked(loadTranscript).mockReturnValue(job.promise);
  open();
  expect(screen.getByText('文稿加载中…')).toBeTruthy();
  await act(async () => job.resolve(null));
  expect(screen.getByText(/这集的句级文稿暂时没能打开/)).toBeTruthy();
  expect(screen.getByText(/本集暂用章节摘要作阅读稿/)).toBeTruthy();
  expect(screen.queryByText('文稿加载中…')).toBeNull();
});
it('route changes ignore late transcript completion from the previous lecture', async () => {
  const old = pending();
  const next = pending();
  vi.mocked(loadTranscript).mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise);
  open();
  fireEvent.click(screen.getByRole('link', { name: '切换讲次' }));
  await act(async () => old.resolve(file));
  expect(screen.queryByText('已到达的句稿')).toBeNull();
  expect(screen.getByText('文稿加载中…')).toBeTruthy();
  await act(async () => next.resolve(null));
  expect(screen.queryByText('文稿加载中…')).toBeNull();
});

it('a rejected transcript request settles as unavailable, not a permanent spinner', async () => {
  let reject!: (reason: Error) => void;
  vi.mocked(loadTranscript).mockReturnValue(new Promise((_resolve, fail) => { reject = fail; }));
  open();
  expect(screen.getByText('文稿加载中…')).toBeTruthy();
  await act(async () => reject(new Error('transcript unavailable')));
  expect(screen.getByText(/这集的句级文稿暂时没能打开/)).toBeTruthy();
  expect(screen.queryByText('文稿加载中…')).toBeNull();
});
it('a loaded lecture cannot leave old sentences beside the next lecture loading notice', async () => {
  const next = pending();
  vi.mocked(loadTranscript).mockResolvedValueOnce(file).mockReturnValueOnce(next.promise);
  open();
  await screen.findByText('已到达的句稿');
  fireEvent.click(screen.getByRole('link', { name: '切换讲次' }));
  expect(screen.queryByText('已到达的句稿')).toBeNull();
  expect(screen.getByText('文稿加载中…')).toBeTruthy();
  await act(async () => next.resolve(null));
  expect(screen.queryByText('文稿加载中…')).toBeNull();
});
