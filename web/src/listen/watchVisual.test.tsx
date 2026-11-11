import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WatchPage } from '../pages/listen/WatchPage';
const css = readFileSync(new URL('../listen.css', import.meta.url), 'utf8');
// Source contract covers media overrides; jsdom cannot verify real layout.
function values(selector: string, property: string) {
  return [...css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, selectors]) => selectors.split(',').some(s => s.trim() === selector))
    .flatMap(([, , body]) => body.split(';').flatMap(d => {
      const colon = d.indexOf(':');
      return d.slice(0, colon).trim() === property ? [d.slice(colon + 1).trim()] : [];
    }));
}
it('watch title uses the desk title/display scale, not a small reading heading', () => {
  expect(values('.listen-desk--watch .player-title', 'font-size')).toEqual([
    'clamp(var(--desk-text-title), 3.6vw, var(--desk-text-display))',
  ]);
  expect(values('.player-title', 'font-weight')).toEqual(['700']);
  expect(values('.player-title', 'letter-spacing')).toEqual(['-0.02em']);
});
it('ordinary and selected sentences have distinct tokenized scales at every breakpoint', () => {
  expect(values('.utter-body p', 'font-size')).toEqual(['var(--desk-text-reading)']);
  expect(values('.utter-body p', 'line-height')).toEqual(['var(--desk-leading-reading)']);
  expect(values('.utter-body p', 'color')).toEqual(['var(--desk-text-reading-color)']);
  expect(values('.utter-row.active .utter-body p', 'font-size')).toEqual(['var(--desk-text-selected)']);
  expect(values('.utter-row.active .utter-body p', 'line-height')).toEqual(['var(--desk-leading-selected)']);
  expect(values('.utter-row.active .utter-body p', 'font-weight')).toEqual(['600']);
  expect(values('.utter-row.active::before', 'background')).toEqual(['var(--primary)']);
  expect(values('.utter-row.active', 'background')).toEqual(['var(--surface)']);
});
it('centers readable transcription tabs; no invented knowledge tab', () => {
  expect(values('.script-tabs', 'justify-content')).toEqual(['center']);
  expect(values('.script-tabs button', 'font-size')).toEqual(['var(--desk-text-tab)']);
  expect(values('.script-tabs button', 'border-bottom')).toEqual(['3px solid transparent']);
  const html = renderToStaticMarkup(<MemoryRouter initialEntries={['/watch/shl-001']}>
    <Routes><Route path="/watch/:videoId" element={<WatchPage />} /></Routes>
  </MemoryRouter>);
  expect(html).toMatch(/class="active"[^>]*>转写<\/button>/);
  expect(html).not.toMatch(/<button[^>]*>本集知识点<\/button>/);
  expect(html).toMatch(/class="player-card"[\s\S]*class="series-chip"[\s\S]*class="player-title"/);
});
it('never restores desktop split columns or another watch scroll owner', () => {
  expect(values('.listen-desk--watch .listen-stage-watch', 'flex-direction')).toEqual(['column']);
  expect(values('.watch-fixed', 'width')).toEqual(['100%']);
  expect(values('.listen-desk--watch .watch-fixed', 'width')).toEqual([]);
  expect(values('.script-scroll', 'overflow-y')).toEqual(['auto']);
  for (const selector of ['.listen-desk--watch', '.listen-desk--watch .listen-main', '.listen-desk--watch .listen-stage-watch', '.listen-desk--watch .script-section']) {
    expect(values(selector, 'overflow')).toEqual(['hidden']);
  }
});

it('desk scale keeps readable 18px ordinary / 22–24px selected / 32–36px title hierarchy', () => {
  const tokens = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  for (const declaration of ['--desk-text-reading: 18px', '--desk-text-selected: 24px',
    '--desk-text-title: 32px', '--desk-text-display: 36px', '--desk-leading-reading: 1.8',
    '--desk-leading-selected: 1.7', '--desk-text-tab: 17px']) {
    expect(tokens).toContain(declaration);
  }
  expect(values('.listen-stage-watch', '--desk-text-selected')).toEqual(['22px']);
});
