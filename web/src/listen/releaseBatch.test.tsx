// @vitest-environment jsdom
/// <reference types="node" />
// Actual committed release -> HTTP adapter -> SearchPage -> router -> WatchPage.
// jsdom does NOT fetch iframe resources or prove visual/YouTube playback success.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import receipt from '../../../docs/releases/pr6-jgy-013-015.audit.json';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { ComponentType } from 'react';

let SearchPage: ComponentType;
let WatchPage: ComponentType;
beforeEach(async () => {
  vi.resetModules();
  localStorage.clear();
  Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, writable: true, value: vi.fn() });
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} });
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (!/^\/(transcripts|knowledge|entities)\/[a-z]+-\d{3}\.json$/.test(url)) throw new Error(`Unexpected network: ${url}`);
    // Files are the real published bytes, not a substitute for business logic.
    const raw = readFileSync(resolve(process.cwd(), 'public', url.slice(1)), 'utf8');
    return new Response(raw, { headers: { 'content-type': 'application/json' } });
  }));
  ({ SearchPage } = await import('../pages/listen/SearchPage'));
  ({ WatchPage } = await import('../pages/listen/WatchPage'));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function Location() { const l = useLocation(); return <output data-testid="route">{l.pathname}{l.search}</output>; }

it.each(receipt.episodes)('new $video_id actual quote is searchable and opens a truthful second request', async ({ video_id, sample }) => {
  render(<MemoryRouter initialEntries={[`/search?q=${encodeURIComponent(sample.text)}`]}><Location /><Routes>
    <Route path="/search" element={<SearchPage />} /><Route path="/watch/:videoId" element={<WatchPage />} />
  </Routes></MemoryRouter>);
  const hit = (await screen.findByText(sample.text)).closest('article')!;
  const target = `/watch/${video_id}?t=${Math.floor(sample.start_s)}`;
  const link = within(hit).getByRole('link', { name: /^从 / });
  expect(link.getAttribute('href')).toBe(target);
  fireEvent.click(link);
  expect(screen.getByTestId('route').textContent).toBe(target);
  expect(await screen.findByText(sample.text)).toBeTruthy();
  expect(document.querySelector('iframe')).toBeNull();
  expect(screen.queryByText(/暂未公开句稿|没能打开/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '点这里听' }));
  await waitFor(() => expect(document.querySelector('iframe')).not.toBeNull());
  const src = new URL(document.querySelector('iframe')!.src);
  expect(src.hostname).toBe('www.youtube.com');
  expect(src.searchParams.get('start')).toBe(String(Math.floor(sample.start_s)));
  const { getLecture } = await import('./lectures');
  expect(src.pathname).toBe(`/embed/${getLecture(video_id)!.youtubeId}`);
  expect(document.querySelector('.progress-fill,[role="progressbar"]')).toBeNull();
  expect(document.body.textContent).not.toMatch(/正在播放|已播放|播放成功|28%/);
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url) === `/transcripts/${video_id}.json`)).toBe(true);
}, 10000);
