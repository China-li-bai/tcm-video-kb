// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { GraphPage } from '../pages/GraphPage';
import { PathsPage } from '../pages/PathsPage';
import { DetailPanel } from '../panel/DetailPanel';
import { fetchPaths, fetchSubgraph } from '../api/client';
import type { PathsResponse, Subgraph } from '../types';
vi.mock('../api/client', () => ({ fetchPaths: vi.fn(), fetchSubgraph: vi.fn(), ApiError: class extends Error {} }));
// Only canvas is mocked; real selection, panels, adapter and citation links render.
vi.mock('./GraphApp', () => ({ GraphApp: ({ onSelect }: { onSelect: (s: {kind: 'edge'; id: string}) => void }) =>
  <button onClick={() => onSelect({kind: 'edge', id: 'edge.test'})}>点选关系</button> }));
const cite = { kp_id: 'shl-001.kp0069', video_id: 'shl-001', start_s: 125, quote: '桂枝汤调和阴阳。' };
const held = [{ kp_id: 'shl-001.kpHeld', video_id: 'shl-001', kp_type: 'formula_indication', pred: 'treats',
  subj_ids: ['formula.gui_zhi_tang'], obj_ids: ['syndrome.test'], subj_labels: ['桂枝汤'], obj_labels: ['太阳中风'],
  reasons: ['confidence 0.85 < 0.90', 'evidence 3 < 12', 'window 4.2s < 15s'], confidence: 0.85,
  statement: '桂枝汤与太阳中风的讲法', evidence_quote: '这是待核对的原句。', citation: cite }];
const graph: Subgraph = { focus: 'formula.gui_zhi_tang', disclaimer: 'candidate threshold 0.90',
  nodes: [{ id: 'formula.gui_zhi_tang', label: '桂枝汤', category: 'formula', citations: [cite] },
    { id: 'syndrome.test', label: '太阳中风', category: 'syndrome', citations: [] }],
  edges: [{ id: 'edge.test', subj_id: 'formula.gui_zhi_tang', obj_id: 'syndrome.test', pred: 'treats', source: 'lecture',
    review_status: 'candidate', confidence: 0.91, kp_id: cite.kp_id, evidence_quote: cite.quote, citation: cite }], held };
const card = { subj_id: 'pulse.fu', obj_id: 'syndrome.test', label: '脉浮', category: 'pulse', pred: 'indicates',
  kp_id: cite.kp_id, review_status: 'candidate', video_id: 'shl-001', start_s: 125, evidence_quote: '脉浮是原讲中的线索。' };
const paths: PathsResponse = { focus: 'syndrome.test', equal_weight: true, disclaimer: 'candidate 过阈进入检索；confidence 0.90',
  tracks: [{ syndrome_id: 'syndrome.test', label: '太阳中风', cards: [card], treats: [] },
    { syndrome_id: 'syndrome.other', label: '另一讲法', cards: [{ ...card, subj_id: 'symptom.han', label: '汗出' }], treats: [] }], held };
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function open(page: React.ReactNode) { return render(<MemoryRouter>{page}</MemoryRouter>); }
// Ignore collapsed developer inputs, but inspect actual rendered learner text.
function readingText() {
  const clone = document.body.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('details:not([open])').forEach(d => { d.textContent = d.querySelector('summary')?.textContent ?? ''; });
  return clone.textContent ?? '';
}
function plainReading() { expect(readingText()).not.toMatch(/formula\.gui_zhi_tang|shl-001\.kp|confidence|candidate|阈|硬闸|未入图|·API|接口|\bcite\b|evidence|window|badge|indicates/); }
it('graph keeps playback, legend and clear selection without technical metadata', async () => {
  vi.mocked(fetchSubgraph).mockResolvedValue(graph); open(<GraphPage/>);
  await screen.findByRole('button', {name:'点选关系'}); plainReading();
  expect(screen.getByLabelText('图例')).toBeTruthy();
  expect(screen.getAllByRole('link', {name:/听原讲/}).every(a => a.getAttribute('href') === '/watch/shl-001?t=125')).toBe(true);
  expect(screen.getByText(/还没有足够把握画进图里/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', {name:'清除选中'}));
  expect(screen.getByRole('button', {name:'清除选中'}).hasAttribute('disabled')).toBe(true); plainReading();
});
it('relationship uses endpoint names and keeps the unverified qualification', async () => {
  vi.mocked(fetchSubgraph).mockResolvedValue(graph); open(<GraphPage/>);
  fireEvent.click(await screen.findByRole('button', {name:'点选关系'}));
  expect(screen.getByText('桂枝汤 → 太阳中风')).toBeTruthy();
  expect(screen.getByText(/尚待核对/)).toBeTruthy();
  expect(screen.getByText('「桂枝汤调和阴阳。」')).toBeTruthy(); plainReading();
});
it('unknown category and missing endpoints do not fall back to internal codes', () => {
  open(<DetailPanel subgraph={{...graph, nodes:[]}} selection={{kind:'edge', id:'edge.test'}} onClear={() => {}}/>); plainReading(); cleanup();
  open(<DetailPanel subgraph={{...graph, held:[], nodes:[{...graph.nodes[0], category:'experimental_type'}]}} selection={{kind:'node', id:graph.focus}} onClear={() => {}}/>);
  expect(readingText()).not.toContain('experimental_type');
});
it('paths keep all/single-track tabs, symptom highlight/clear, mini summary and playback', async () => {
  vi.mocked(fetchPaths).mockResolvedValue(paths); open(<PathsPage/>);
  await screen.findByRole('tab', {name:/全部/}); plainReading();
  expect(screen.getByRole('tab', {name:/全部/}).getAttribute('aria-selected')).toBe('true');
  fireEvent.click(within(screen.getByRole('group', {name:/症组筛选/})).getByRole('button', {name:'脉浮'}));
  expect(document.querySelectorAll('.hyp-card.is-muted')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', {name:'清除筛选'}));
  expect(document.querySelectorAll('.hyp-card.is-muted')).toHaveLength(0);
  fireEvent.click(screen.getByRole('tab', {name:/^太阳中风/}));
  expect(document.querySelectorAll('.hyp-card')).toHaveLength(1);
  expect(screen.getByText('关系图摘要（辅）')).toBeTruthy();
  expect(screen.getAllByRole('link', {name:/听原讲/}).length).toBeGreaterThan(0);
});
it('compare is a semantic reading table with quotes and station links, and returns to cards', async () => {
  vi.mocked(fetchPaths).mockResolvedValue(paths); open(<PathsPage/>);
  fireEvent.click(await screen.findByRole('button', {name:'对比表'}));
  const table = screen.getByRole('table');
  expect(within(table).getAllByRole('columnheader')).toHaveLength(3);
  expect(within(table).getAllByText('「脉浮是原讲中的线索。」')).toHaveLength(2);
  expect(within(table).getAllByRole('link', {name:/听原讲/})).toHaveLength(2); plainReading();
  fireEvent.click(screen.getByRole('button', {name:'路径卡片'}));
  expect(document.querySelectorAll('.hyp-card')).toHaveLength(2);
});
it('demo supplements remain honestly marked, without internal knowledge-point IDs', async () => {
  vi.mocked(fetchPaths).mockResolvedValue({...paths, focus:'formula.gui_zhi_tang', tracks:[]}); open(<PathsPage/>);
  await screen.findByRole('tab', {name:/伤寒六经/});
  expect(screen.getAllByText(/演示补充/).length).toBeGreaterThan(0); plainReading();
  fireEvent.click(screen.getByRole('button', {name:'对比表'})); plainReading();
});
it('empty symptom filters explain the gap to learners', async () => {
  vi.mocked(fetchPaths).mockResolvedValue({...paths, tracks:[]}); open(<PathsPage/>);
  await screen.findByRole('tab', {name:/全部/}); plainReading();
  expect(screen.getByText('这段讲法暂未整理症组。')).toBeTruthy();
});
it('unrecognized path type stays a plain reading label, never an English type key', async () => {
  vi.mocked(fetchPaths).mockResolvedValue({...paths, tracks:[{...paths.tracks[0], cards:[{...card, category:'experimental_type'}]}]});
  open(<PathsPage/>);
  await screen.findByRole('tab', {name:/全部/});
  expect(readingText()).not.toContain('experimental_type');
});
