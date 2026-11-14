import { afterEach, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WatchPage } from '../pages/listen/WatchPage';
import { ListenHomePage } from '../pages/listen/ListenHomePage';
import { CheckSheet } from './CheckSheet';
import { getChapters } from './chapters';

function watch(path: string) {
  return renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><Routes><Route path="/watch/:videoId" element={<WatchPage />} /></Routes></MemoryRouter>);
}
afterEach(() => vi.unstubAllGlobals());

it('describes URL time as a requested position, never a measured progress bar', () => {
  const html = watch('/watch/shl-001?t=125');
  expect(html).toContain('请求定位 02:05');
  expect(html).not.toContain('28%');
  expect(html).not.toContain('progress-fill');
  expect(html).not.toContain('role="progressbar"');
});
it('explains that selected text is not synchronized with continuous playback', () => {
  const html = watch('/watch/shl-001?t=125');
  expect(html).toContain('文稿高亮只表示所选位置，不会跟着播放自动翻页');
  expect(html).not.toContain('回到正在播放');
});
it('does not open an iframe or claim playback before an explicit request', () => {
  const html = watch('/watch/shl-001?t=125');
  expect(html).not.toContain('<iframe');
  expect(html).toContain('尚未打开播放器');
});
it.each(['Infinity', '-20', 'not-a-number'])('normalizes invalid URL seconds %s honestly', t => {
  const html = watch(`/watch/shl-001?t=${t}`);
  expect(html).toContain('请求定位 00:00');
  expect(html).not.toContain('NaN');
});
it('resume means last opened/requested position, not last heard or completed', () => {
  vi.stubGlobal('localStorage', {getItem: (key: string) => key.includes('lastWatch') ? JSON.stringify({videoId:'shl-001', title:'原讲', t:125.9, updatedAt:'2026-11-09'}) : null});
  const html = renderToStaticMarkup(<MemoryRouter><ListenHomePage /></MemoryRouter>);
  expect(html).toContain('上次打开的位置');
  expect(html).toContain('/watch/shl-001?t=125');
  expect(html).toContain('不是播放进度');
  expect(html).not.toContain('上次听到');
});
it('nearby claims are exported knowledge, not an assertion of human review', () => {
  const html = renderToStaticMarkup(<CheckSheet open quote="原句" where="本集" t={125} claims={[{kp_id:'shl-001.kp1',video_id:'shl-001',type:'claim',statement:'原主张',evidence_quote:'短证据',start_s:125,end_s:130,confidence:0.9}]} onClose={()=>{}} onListen={()=>{}} onStash={()=>{}} />);
  expect(html).toContain('从本集知识点里摘出的主张');
  expect(html).not.toContain('已经核对过');
});

it.each(['shl-001','jgy-001'])('keeps a real fractional chapter boundary selected after floor-to-second navigation: %s', videoId => {
  const chapter = getChapters(videoId)[1];
  expect(chapter.start_s % 1).not.toBe(0);
  const html = watch(`/watch/${videoId}?t=${Math.floor(chapter.start_s)}`);
  expect(html).toContain(renderToStaticMarkup(<h1 className="player-title">{chapter.title}</h1>));
});
