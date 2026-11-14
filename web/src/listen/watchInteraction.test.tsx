// @vitest-environment jsdom
// jsdom's default resources are disabled: iframe URLs are inspected, never fetched.
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { ComponentType } from 'react';
import { getChapters } from './chapters';

let WatchPage: ComponentType;
let ListenHomePage: ComponentType;
let unavailable = false;
let deferred: Promise<Response> | null = null;
const scrollIntoView = vi.fn();
const intersectionCallbacks: IntersectionObserverCallback[] = [];
const secondChapter = getChapters('shl-001')[1];
const boundary = secondChapter.start_s;
const segments = [
  {seq:0,start_s:124.1,end_s:125.6,text:'前一句测试'},
  {seq:1,start_s:125.8,end_s:130,text:'点击的小数句'},
  {seq:2,start_s:140.25,end_s:146,text:'另一处句子'},
  {seq:3,start_s:boundary+0.2,end_s:boundary+5,text:'第二章开头句'},
];
const json = (body: unknown) => new Response(JSON.stringify(body), {headers:{'content-type':'application/json'}});

beforeEach(async () => {
  vi.resetModules();
  localStorage.clear();
  unavailable = false;
  deferred = null;
  scrollIntoView.mockClear();
  intersectionCallbacks.length = 0;
  vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(scrollIntoView);
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: IntersectionObserverCallback) { intersectionCallbacks.push(callback); }
    observe() {} unobserve() {} disconnect() {}
  });
  vi.stubGlobal('fetch', vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    // Any unexpected/external URL is a hard failure, not a live-network fallback.
    const match = /^\/(transcripts|knowledge|entities)\/([\w-]+)\.json$/.exec(url);
    if (!match) throw new Error(`Unexpected network request: ${url}`);
    const [,layer,videoId] = match;
    if (layer === 'transcripts') {
      if (deferred) return deferred;
      if (unavailable) return new Response('<html>SPA fallback</html>', {headers:{'content-type':'text/html'}});
      if (videoId === 'zj-002') return new Response('{}', {status:404,headers:{'content-type':'application/json'}});
      return json({video_id:videoId,segments});
    }
    return json({video_id:videoId,[layer === 'knowledge' ? 'points' : 'mentions']:[]});
  }));
  ({WatchPage} = await import('../pages/listen/WatchPage'));
  ({ListenHomePage} = await import('../pages/listen/ListenHomePage'));
});
afterEach(() => {
  cleanup();
  expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(0);
  expect(vi.mocked(fetch).mock.calls.every(([input]) => /^\/(transcripts|knowledge|entities)\/(shl-001|jgy-001|zj-002)\.json$/.test(String(input)))).toBe(true);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
// Not layout support: observe only that the component wires an observer and scroll callback.
Object.defineProperty(Element.prototype, 'scrollIntoView', {configurable:true,writable:true,value:()=>{}});
function LocationProbe() {
  const {pathname,search} = useLocation();
  return <output data-testid="location">{pathname}{search}</output>;
}
function open(path='/watch/shl-001?t=100') {
  return render(<MemoryRouter initialEntries={[path]}>
    <nav><Link to="/watch/jgy-001?t=250">切换测试讲次</Link><Link to="/watch/shl-001?t=125">返回测试讲次</Link></nav>
    <LocationProbe />
    <Routes><Route path="/watch/:videoId" element={<WatchPage />} /><Route path="/" element={<ListenHomePage />} /></Routes>
  </MemoryRouter>);
}
function frame() { return document.querySelector('iframe')!; }
function lastPosition() { return JSON.parse(localStorage.getItem('renji.listen.lastWatch.v1')!); }
async function clickSentence(text='点击的小数句') {
  const row = (await screen.findByText(text)).closest('[role="button"]')!;
  fireEvent.click(row);
  await waitFor(() => expect(frame()).not.toBeNull());
  return row;
}
function noFakeProgress() {
  expect(document.querySelector('.progress-fill,[role="progressbar"]')).toBeNull();
  expect(document.body.textContent).not.toMatch(/正在播放|已播放|播放成功|跳秒成功了|已完成|28%/);
}

it('clicks a real transcript row through effects/router/storage and updates iframe requested seconds', async () => {
  open();
  expect(frame()).toBeNull();
  const row = await clickSentence();
  expect(row.getAttribute('aria-pressed')).toBe('true');
  expect(screen.getByTestId('location').textContent).toBe('/watch/shl-001?t=125');
  expect(screen.getByText('请求定位 02:05')).toBeTruthy();
  expect(new URL(frame().src).searchParams.get('start')).toBe('125');
  expect(new URL(frame().src).searchParams.get('autoplay')).toBe('1');
  expect(lastPosition().t).toBe(125);
  const fallback = screen.getByRole('link',{name:'播不了？用原平台听'}) as HTMLAnchorElement;
  expect(new URL(fallback.href).searchParams.get('t')).toBe('125s');
  await clickSentence('另一处句子');
  expect(new URL(frame().src).searchParams.get('start')).toBe('140');
  expect(lastPosition().t).toBe(140);
  noFakeProgress();
});
it('chooses the real fractional chapter boundary, then its transcript row without snapping back', async () => {
  open();
  await screen.findByText('点击的小数句');
  fireEvent.click(screen.getByRole('button',{name:'章'}));
  fireEvent.click(screen.getByText(secondChapter.title,{selector:'.chapter-title'}).closest('button')!);
  await screen.findByText('第二章开头句');
  expect(screen.getByRole('heading',{level:1}).textContent).toBe(secondChapter.title);
  expect(screen.getByTestId('location').textContent).toBe(`/watch/shl-001?t=${Math.floor(boundary)}`);
  expect(new URL(frame().src).searchParams.get('start')).toBe(String(Math.floor(boundary)));
  expect(lastPosition().chapterId).toBe(secondChapter.chapter_id);
  const row = await clickSentence('第二章开头句');
  expect(row.getAttribute('aria-pressed')).toBe('true');
  expect(screen.getByRole('heading',{level:1}).textContent).toBe(secondChapter.title);
  noFakeProgress();
});
it('keeps the exact URL request in storage when delayed transcript effects select a different sentence start', async () => {
  let resolve!: (response: Response) => void;
  deferred = new Promise<Response>(done => {resolve=done;});
  open('/watch/shl-001?t=128');
  expect(screen.getByText('文稿加载中…')).toBeTruthy();
  expect(lastPosition().t).toBe(128);
  await act(async () => resolve(json({video_id:'shl-001',segments})));
  await screen.findByText('点击的小数句');
  expect(lastPosition().t).toBe(128);
  expect(frame()).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'点这里听'}));
  expect(new URL(frame().src).searchParams.get('start')).toBe('128');
});
it('shows an uncovered transcript honestly after actual 404 without fabricating rows or playback', async () => {
  open('/watch/zj-002?t=125');
  expect(await screen.findByText('这集还没有对齐好的文稿。')).toBeTruthy();
  expect(document.querySelector('.utter-row')).toBeNull();
  expect(frame()).toBeNull();
  expect(lastPosition().t).toBe(125);
  noFakeProgress();
});
it('shows a published transcript load failure for 200 HTML; any fallback is labelled summary, not raw sentences', async () => {
  unavailable = true;
  open();
  expect(await screen.findByText(/这集的句级文稿暂时没能打开/)).toBeTruthy();
  expect(screen.getByText(/本集暂用章节摘要作阅读稿/)).toBeTruthy();
  expect(screen.queryByText('点击的小数句')).toBeNull();
  noFakeProgress();
});
it('wires error/retry/load to the actual iframe without claiming media readiness or moving selection', async () => {
  open();
  const row = await clickSentence();
  const initial = frame();
  fireEvent.error(initial);
  expect(screen.getByText(/未能打开播放器页面/)).toBeTruthy();
  fireEvent.load(initial);
  expect(screen.getByText(/未能打开播放器页面/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'重新请求此位置'}));
  const retried = frame();
  expect(retried).not.toBe(initial);
  expect(retried.src).toBe(initial.src);
  expect(screen.getByText(/尚未收到页面响应/)).toBeTruthy();
  fireEvent.load(retried);
  expect(screen.getByText(/播放器页面有响应；本站不能确认播放或跳秒是否成功/)).toBeTruthy();
  expect(row.getAttribute('aria-pressed')).toBe('true');
  expect(lastPosition().t).toBe(125);
  noFakeProgress();
});
it.each(['Enter',' '])('does not accidentally retry/start iframe when a nested text action receives %j', async key => {
  open();
  await clickSentence();
  const initial = frame();
  fireEvent.error(initial);
  const more = screen.getByRole('button',{name:'这句还能做什么'});
  fireEvent.keyDown(more,{key});
  fireEvent.click(more); // jsdom does not synthesize browser default keyboard click.
  expect(screen.getByRole('button',{name:'问这句'})).toBeTruthy();
  expect(frame()).toBe(initial);
  expect(screen.getByText(/未能打开播放器页面/)).toBeTruthy();
});
it('wires selected-row return scroll without a new seek, and clears iframe intent on route changes', async () => {
  open();
  await clickSentence();
  const initial = frame();
  expect(intersectionCallbacks.length).toBeGreaterThan(0);
  act(() => intersectionCallbacks.at(-1)!([{isIntersecting:false} as IntersectionObserverEntry],{} as IntersectionObserver));
  const before = scrollIntoView.mock.calls.length;
  fireEvent.click(screen.getByRole('button',{name:'回到所选句'}));
  expect(scrollIntoView.mock.calls.length).toBe(before+1);
  expect(frame()).toBe(initial);
  fireEvent.click(screen.getByRole('link',{name:'切换测试讲次'}));
  await waitFor(() => expect(lastPosition().videoId).toBe('jgy-001'));
  expect(frame()).toBeNull();
  expect(lastPosition().t).toBe(250);
  fireEvent.click(screen.getByRole('link',{name:'返回测试讲次'}));
  await waitFor(() => expect(lastPosition().videoId).toBe('shl-001'));
  expect(frame()).toBeNull();
  expect(lastPosition().t).toBe(125);
  fireEvent.click(screen.getByRole('link',{name:'回首页'}));
  expect(await screen.findByText('上次打开的位置')).toBeTruthy();
  expect(screen.getByRole('link',{name:/上次打开的位置/}).getAttribute('href')).toBe('/watch/shl-001?t=125');
});

it.each(['Enter',' '])('still activates the transcript row itself via keyboard %j', async key => {
  open();
  const row = (await screen.findByText('点击的小数句')).closest('[role="button"]')!;
  fireEvent.keyDown(row,{key});
  await waitFor(() => expect(frame()).not.toBeNull());
  expect(new URL(frame().src).searchParams.get('start')).toBe('125');
  expect(row.getAttribute('aria-pressed')).toBe('true');
  expect(lastPosition().t).toBe(125);
  noFakeProgress();
});
