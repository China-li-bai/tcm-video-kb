// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ListenHomePage } from '../pages/listen/ListenHomePage';
import { SeriesPage } from '../pages/listen/SeriesPage';
import { SeriesDetailPage } from '../pages/listen/SeriesDetailPage';
import { getAllLectures, getSeriesGroups, formatDurationLabel, pickTodaySegment } from './lectures';

// jsdom cannot measure responsive layout: assert token consumption / wrapping
// contracts, not pixel snapshots. Browser + real-device review remains required.
const css = readFileSync(`${process.cwd()}/src/listen.css`, 'utf8');
function values(selector: string, property: string) {
  return [...css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, selectors]) => selectors.split(',').some(s => s.trim() === selector))
    .flatMap(([, , body]) => body.split(';').flatMap(d => {
      const i = d.indexOf(':'); return d.slice(0, i).trim() === property ? [d.slice(i + 1).trim()] : [];
    }));
}
function open(path: string) {
  render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/" element={<ListenHomePage />} />
    <Route path="/series" element={<SeriesPage />} />
    <Route path="/series/:seriesId" element={<SeriesDetailPage />} />
  </Routes></MemoryRouter>);
}
beforeEach(() => localStorage.clear());
afterEach(cleanup);

it('home keeps the narrow stage, a dominant title/action and generous tokenized rhythm', () => {
  open('/');
  expect(document.querySelector('.listen-home[data-desk-stage="narrow"]')).toBeTruthy();
  expect(screen.getByRole('heading', { level: 1 }).className).toBe('today-title');
  expect(screen.getByRole('link', { name: '开始听' }).className).toContain('listen-btn-lg');
  expect(values('.today-title', 'font-size')).toContain('clamp(var(--desk-text-title), 5vw, var(--desk-text-display))');
  expect(values('.today-card', 'border-radius')).toEqual(['var(--desk-radius-hero)']);
  expect(values('.listen-home', 'gap')).toContain('var(--desk-space-10)');
  expect(values('.listen-btn-lg', 'font-size')).toEqual(['var(--desk-text-reading)']);
});
it('whole-lecture recommendations keep their true durations and circular play cues; no fake resume', () => {
  open('/');
  expect(screen.queryByText('接着听')).toBeNull();
  const today = pickTodaySegment().lecture;
  const next = getAllLectures().filter(l => l.series === today.series && l.id !== today.id).slice(0, 2);
  const rows = [...document.querySelectorAll('.upnext-row')];
  expect(rows).toHaveLength(next.length);
  rows.forEach((row, i) => {
    expect(row.getAttribute('href')).toBe(`/watch/${next[i].id}`);
    if (next[i].duration) expect(row.textContent).toContain(next[i].duration);
    expect(row.querySelector('.upnext-ico[aria-hidden]')).toBeTruthy();
    expect(row.textContent).not.toMatch(/约 [0-9]+ 分/);
  });
  expect(values('.upnext-row', 'border-radius')).toContain('var(--desk-radius-lg)');
  expect(values('.listen-home .stash-entry', 'border-radius')).toContain('var(--desk-radius-lg)');
});
it('graph/path remain reachable but are separate secondary evidence links, not equal primary links', () => {
  open('/');
  expect(screen.getByRole('link', { name: '全部课程系列' }).closest('.home-evidence-links')).toBeNull();
  for (const name of ['方证图', '路径']) expect(screen.getByRole('link', { name }).closest('.home-evidence-links')).toBeTruthy();
});
it('series cards use source-backed full names, shared illustrated covers, and actual counts', () => {
  open('/series');
  const names: Record<string, string> = { shl: '伤寒论', jgy: '金匮要略', bc: '神农本草经', zj: '针灸大成', nj: '黄帝内经' };
  for (const g of getSeriesGroups()) {
    const card = screen.getByRole('heading', { name: names[g.id] || g.label }).closest('a')!;
    expect(card.getAttribute('href')).toBe(`/series/${g.id}`);
    expect(within(card).getByText(`${g.count} 集`)).toBeTruthy();
    expect(within(card).getByText(g.blurb)).toBeTruthy();
    expect(card.querySelector('.series-cover svg')).toBeTruthy();
    expect(card.querySelector('.series-cover')!.textContent).not.toBe(g.label.slice(0, 1));
  }
  expect(values('.series-card', 'border-radius')).toEqual(['var(--desk-radius-card)']);
  expect(values('.series-cover', 'width')).toEqual(['var(--series-cover-size)']);
  expect(values('.series-cover', 'height')).toEqual(['var(--series-cover-size)']);
  expect(values('.series-card-head h2', 'font-size')).toContain('var(--desk-text-heading)');
});
it('detail uses the same cover/name, complete episode titles and honest existing duration metadata', () => {
  open('/series/shl');
  const g = getSeriesGroups().find(g => g.id === 'shl')!;
  expect(screen.getByRole('heading', { level: 1, name: '伤寒论' })).toBeTruthy();
  expect(document.querySelector('.series-hero-card .series-cover svg')).toBeTruthy();
  const rows = document.querySelectorAll('.episode-row');
  expect(rows).toHaveLength(g.count);
  rows.forEach((row, i) => {
    expect(row.querySelector('h3')!.textContent).toBe(g.lectures[i].title);
    expect(row.getAttribute('href')).toBe(`/watch/${g.lectures[i].id}`);
    if (g.lectures[i].duration) expect(row.textContent).toContain(formatDurationLabel(g.lectures[i].duration));
  });
  expect(values('.ep-body h3', 'white-space')).not.toContain('nowrap');
  expect(values('.ep-body h3', 'font-size')).toContain('var(--desk-text-reading)');
  expect(values('.episode-row', 'padding')).toContain('var(--desk-space-6)');
});

it('desktop proportions remove only page-local gutters, without widening shared stages', () => {
  expect(values('.listen-home', 'padding-inline')).toContain('0');
  expect(values('.listen-series', 'padding-inline')).toContain('0');
  expect(values('.listen-stage-narrow', 'max-width')).toEqual(['var(--desk-stage-narrow)']);
  expect(values('.listen-stage', 'max-width')).toEqual(['var(--desk-stage-default)']);
});
