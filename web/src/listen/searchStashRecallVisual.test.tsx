// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SearchPage } from '../pages/listen/SearchPage';
import { StashPage } from '../pages/listen/StashPage';
import { RecallPage } from '../pages/listen/RecallPage';
import { saveStashItem, STASH_KEY } from './stash';
import { getLecture } from './lectures';
import { searchCatalog, searchQuotes, type SearchHit } from './search';

// Presentation fixtures only. Actual search -> replay remains covered by
// listenDataFlow / releaseBatch. jsdom token contracts are not pixel snapshots.
vi.mock('./search', () => ({ searchCatalog: vi.fn(), searchQuotes: vi.fn() }));
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
    <Route path="/search" element={<SearchPage />} />
    <Route path="/stash" element={<StashPage />} />
    <Route path="/recall/:itemId" element={<RecallPage />} />
  </Routes></MemoryRouter>);
}
const note = () => saveStashItem({ videoId: 'shl-001', title: '合成出处标题', text: '合成待回想原句', t: 125 });
beforeEach(() => {
  localStorage.clear();
  vi.mocked(searchCatalog).mockReturnValue([]);
  vi.mocked(searchQuotes).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('blank search groups its explanation, labelled form and honesty note in one complete card', () => {
  open('/search');
  const card = screen.getByRole('region', { name: '查出处' });
  expect(card.classList.contains('source-search-card')).toBe(true);
  expect(within(card).getByText(/别处听到的/)).toBeTruthy();
  expect(within(card).getByRole('textbox', { name: '想查的原句或关键词' })).toBeTruthy();
  expect(within(card).getByText(/不编造出处/)).toBeTruthy();
  expect(document.querySelector('.listen-search-page[data-desk-stage="narrow"]')).toBeTruthy();
  expect(searchQuotes).not.toHaveBeenCalled();
});
it('no match stays honest in a full state card with reset and station return', async () => {
  open('/search?q=合成无命中');
  const heading = await screen.findByRole('heading', { name: '暂时找不到可靠出处' });
  const card = heading.closest<HTMLElement>('.desk-state-card')!;
  expect(card).toBeTruthy();
  expect(within(card).getByText(/不会编造出处/)).toBeTruthy();
  expect(within(card).getByRole('link', { name: '回听课台' }).getAttribute('href')).toBe('/');
  expect(document.querySelector('.hit-card')).toBeNull();
  fireEvent.click(within(card).getByRole('button', { name: '换说法' }));
  expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('');
});
it('quote hits promote the actual sentence, keep source secondary and preserve replay', async () => {
  const hit: SearchHit = { key: 'fixture', kind: 'quote', lecture: getLecture('shl-001')!,
    href: '/watch/shl-001?t=125', title: '合成出处标题', snippet: '合成命中原句', startS: 125 };
  vi.mocked(searchQuotes).mockResolvedValue([hit]); open('/search?q=合成');
  const quote = await screen.findByText(hit.snippet);
  expect(quote.classList.contains('hit-quote')).toBe(true);
  const card = quote.closest('article')!;
  expect(within(card).getByRole('heading', { name: hit.title }).classList.contains('hit-source-title')).toBe(true);
  expect(within(card).getByRole('link', { name: '从 02:05 听' }).getAttribute('href')).toBe(hit.href);
});
it('empty stash has a full state card, today action and separate local backup', () => {
  open('/stash');
  const card = screen.getByRole('region', { name: '匣子还是空的' });
  expect(card.classList.contains('desk-state-card')).toBe(true);
  expect(within(card).getByText(/听的时候可以收下几句/)).toBeTruthy();
  expect(within(card).getByRole('link', { name: '去听今日一小段' }).getAttribute('href')).toBe('/');
  expect(within(card).queryByRole('region', { name: '学习记录备份' })).toBeNull();
  expect(screen.getByRole('region', { name: '学习记录备份' })).toBeTruthy();
  expect(document.querySelector('.listen-stash[data-desk-stage="narrow"]')).toBeTruthy();
});
it('stash retains recall / replay / remove and the existing storage format', () => {
  const item = note(); open('/stash');
  const card = screen.getByText(item.text).closest('article')!;
  expect(within(card).getByRole('link', { name: '先回想' }).getAttribute('href')).toBe(`/recall/${item.id}`);
  expect(within(card).getByRole('link', { name: '听原讲' }).getAttribute('href')).toBe('/watch/shl-001?t=125');
  fireEvent.click(within(card).getByRole('button', { name: '移出' }));
  expect(JSON.parse(localStorage.getItem(STASH_KEY)!)).toEqual([]);
  expect(screen.getByRole('heading', { name: '匣子还是空的' })).toBeTruthy();
});
it('recall centers a tokenized sentence while preserving conceal / reveal and resave', () => {
  const item = note(); const original = localStorage.getItem(STASH_KEY); open(`/recall/${item.id}`);
  expect(document.querySelector('.listen-recall[data-desk-stage="narrow"]')).toBeTruthy();
  const quote = screen.getByText(item.text);
  expect(quote.classList.contains('recall-quote')).toBe(true);
  expect(quote.classList.contains('blur-line')).toBe(true);
  expect(quote.closest('.recall-card')!.classList.contains('reveal')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '先看一眼原句' }));
  expect(quote.closest('.recall-card')!.classList.contains('reveal')).toBe(true);
  expect(localStorage.getItem(STASH_KEY)).toBe(original);
  expect(screen.getByRole('link', { name: '听原讲' }).getAttribute('href')).toBe('/watch/shl-001?t=125');
  fireEvent.click(screen.getByRole('button', { name: '再收下' }));
  // Existing resave dedupes by text + video and remints the id; do not change that logic here.
  const saved = JSON.parse(localStorage.getItem(STASH_KEY)!);
  expect(saved).toHaveLength(1);
  expect(saved[0]).toMatchObject({ videoId: item.videoId, text: item.text, title: item.title, t: item.t });
});
it('missing recall uses a complete state card, without fabricated content', () => {
  open('/recall/missing');
  expect(screen.getByRole('heading', { name: '找不到这句存货' }).closest('.desk-state-card')).toBeTruthy();
  expect(screen.getByRole('link', { name: '回收获匣' }).getAttribute('href')).toBe('/stash');
  expect(document.querySelector('.recall-quote')).toBeNull();
});
it('cards use desk tokens and an explicit sentence/source hierarchy', () => {
  for (const selector of ['.source-search-card', '.desk-state-card']) {
    expect(values(selector, 'background')).toContain('var(--surface)');
    expect(values(selector, 'border-radius')).toContain('var(--desk-radius-hero)');
    expect(values(selector, 'padding')).toContain('var(--desk-space-10)');
  }
  expect(values('.listen-stash .stash-card', 'gap')).toContain('var(--desk-space-6)');
  expect(values('.listen-stash .stash-quote', 'font-size')).toContain('var(--desk-text-heading)');
  expect(values('.hit-quote', 'font-size')).toContain('var(--desk-text-heading)');
  expect(values('.recall-quote', 'font-size')).toContain('var(--desk-text-selected)');
  expect(values('.recall-quote', 'line-height')).toContain('var(--desk-leading-selected)');
  expect(values('.recall-quote', 'overflow-wrap')).toContain('anywhere');
});
it('phone form can shrink/stack and recall actions stack without changing shell positioning', () => {
  expect(values('.source-search-card .search-page-form input', 'min-width')).toContain('0');
  expect(values('.source-search-card .search-page-form', 'flex-direction')).toContain('column');
  expect(values('.listen-recall .recall-card .hit-actions', 'flex-direction')).toContain('column');
  expect(values('.listen-stash .learning-backup', 'position')).not.toContain('fixed');
});
