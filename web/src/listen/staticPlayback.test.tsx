import { expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { StaticYouTubePlayer } from './StaticYouTubePlayer';
import { requestedSeconds, selectedPositionIndex, nextFramePhase, frameNotice } from './staticPlayback';

it.each([['125.9',125], [125.1,125], [0,0], [null,0], ['',0], [-1,0], ['Infinity',0], ['bad',0]])('normalizes requested seconds %s to %s', (value, expected) => {
  expect(requestedSeconds(value)).toBe(expected);
});
it('selection is derived from a requested position, including gaps, not a timer', () => {
  const rows = [{t:10,end:20},{t:30,end:40}];
  expect(selectedPositionIndex(rows, 5)).toBe(0);
  expect(selectedPositionIndex(rows, 25)).toBe(0);
  expect(selectedPositionIndex(rows, 32)).toBe(1);
  expect(selectedPositionIndex([],32)).toBe(0);
});
it('iframe load only means page response, never confirmed play or seek', () => {
  expect(nextFramePhase('pending', {type:'load'})).toBe('responded');
  expect(frameNotice('responded')).toContain('不能确认播放或跳秒是否成功');
});
it('iframe error remains failed until a fresh keyed request', () => {
  const failed = nextFramePhase('pending', {type:'error'});
  expect(failed).toBe('failed');
  expect(nextFramePhase(failed, {type:'load'})).toBe('failed');
  expect(frameNotice(failed)).toContain('未能打开播放器页面');
});
it('not-yet-responded request has an honest retry fallback, not a ready label', () => {
  const html = renderToStaticMarkup(<StaticYouTubePlayer youtubeId="YT" title="原讲" requestedS={125} requested onRequest={()=>{}} />);
  expect(html).toContain('尚未收到页面响应');
  expect(html).toContain('重新请求此位置');
  expect(html).toContain('原平台听');
  expect(html).not.toContain('正在播放');
});
it('distinct requested sentences produce distinct iframe and fallback seek URLs', () => {
  for (const t of [125,250]) {
    const html = renderToStaticMarkup(<StaticYouTubePlayer youtubeId="YT" title="原讲" requestedS={t} requested onRequest={()=>{}} />);
    expect(html).toContain(`start=${t}&amp;autoplay=1`);
    expect(html).toContain(`watch?v=YT&amp;t=${t}s`);
  }
});
it('missing video source has no pretend play/pause control', () => {
  const html = renderToStaticMarkup(<StaticYouTubePlayer youtubeId={null} title="原讲" requestedS={125} requested={false} onRequest={()=>{}} />);
  expect(html).toContain('本集暂无嵌入片源');
  expect(html).not.toContain('<button');
  expect(html).not.toContain('<iframe');
});
it('preserves the clicked row selection when iframe/URL seconds are rounded down', () => {
  const rows = [{key:'previous',t:120,end:125.6},{key:'clicked',t:125.8,end:130}];
  expect(selectedPositionIndex(rows,125,'clicked')).toBe(1);
  expect(selectedPositionIndex(rows,125,'missing')).toBe(0);
});
