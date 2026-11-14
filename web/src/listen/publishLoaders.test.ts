/// <reference types="node" />
import { afterEach, describe, expect, it, vi } from 'vitest';

const cases = [
  ['transcript', 'segments', () => import('./transcript').then(m => m.loadTranscript), { seq: 0, start_s: 1, end_s: 2, text: '原句' }],
  ['knowledge', 'points', () => import('./knowledgePoints').then(m => m.loadKnowledgePoints), { kp_id: 'shl-001.kp0001', video_id: 'shl-001', type: 'claim', statement: '主张', evidence_quote: '证据', start_s: 1, end_s: 2, confidence: 0.9 }],
  ['entities', 'mentions', () => import('./entities').then(m => m.loadEntities), { entity_id: 'formula.test', label: '方', type: 'formula', start_s: 1, end_s: 2, seq: 0 }],
] as const;

afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });
for (const [name, key, getLoader, row] of cases) {
  describe(name, () => {
    const payload = { video_id: 'shl-001', [key]: [row] };
    it.each([
      ['HTML', 200, 'text/html', '<!doctype html>'],
      ['JSON disguised as HTML', 200, 'text/html', JSON.stringify(payload)],
      ['404 JSON', 404, 'application/json', JSON.stringify(payload)],
      ['broken JSON', 200, 'application/json', '{bad'],
      ['wrong video', 200, 'application/json', JSON.stringify({...payload, video_id: 'zj-002'})],
      ['wrong shape', 200, 'application/json', JSON.stringify({video_id: 'shl-001', [key]: {}})],
      ['bad row', 200, 'application/json', JSON.stringify({video_id: 'shl-001', [key]: [{...row, start_s: 'bad'}]})],
      ['reversed time', 200, 'application/json', JSON.stringify({video_id: 'shl-001', [key]: [{...row, end_s: -1}]})],
    ])('rejects %s', async (_label, status, type, body) => {
      const fetcher = vi.fn().mockResolvedValue(new Response(body, { status, headers: {'content-type': type} }));
      vi.stubGlobal('fetch', fetcher);
      const load = await getLoader();
      expect(await load('shl-001')).toBeNull();
      expect(await load('shl-001')).toBeNull();
      expect(fetcher).toHaveBeenCalledTimes(1);
    });
    it('accepts valid JSON and deduplicates concurrent requests', async () => {
      const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { headers: {'content-type': 'application/json; charset=utf-8'} }));
      vi.stubGlobal('fetch', fetcher);
      const load = await getLoader();
      const values = await Promise.all([load('shl-001'), load('shl-001')]);
      expect(values[0]).toEqual(payload);
      expect(values[1]).toEqual(payload);
      expect(fetcher).toHaveBeenCalledTimes(1);
    });
    it('rejects duplicate row identities instead of hiding inconsistencies', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({video_id: 'shl-001', [key]: [row, row]}), {headers: {'content-type': 'application/json'}})));
      expect(await (await getLoader())('shl-001')).toBeNull();
    });
    it('distinguishes an empty optional layer from an unavailable transcript', async () => {
      const empty = {video_id: 'shl-001', [key]: []};
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(empty), {headers: {'content-type': 'application/json'}})));
      const data = await (await getLoader())('shl-001');
      if (key === 'segments') expect(data).toBeNull();
      else expect(data).toEqual(empty);
    });
    it('handles network errors without inventing data', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
      expect(await (await getLoader())('shl-001')).toBeNull();
    });
  });
}

it('derives coverage from actual generated manifest, not another id list', async () => {
  const { default: manifest } = await import('../data/publish-manifest.json');
  const { TRANSCRIPT_VIDEO_IDS } = await import('./transcriptCoverage');
  expect(TRANSCRIPT_VIDEO_IDS).toEqual(manifest.lectures.filter(r => r.has_public_transcript).map(r => r.video_id));
  expect(TRANSCRIPT_VIDEO_IDS).toHaveLength(21);
});

// Exercise the real committed release through the same HTTP validation path.
it('accepts all 63 shipped assets without reducing the 21-episode release', async () => {
  const { readFileSync } = await import('node:fs');
  const { default: manifest } = await import('../data/publish-manifest.json');
  for (const entry of manifest.lectures.filter(r => r.has_public_transcript)) {
    for (const [name, key, getLoader] of cases) {
      const folder = name === 'transcript' ? 'transcripts' : name;
      const raw = readFileSync(new URL(`../../public/${folder}/${entry.video_id}.json`, import.meta.url), 'utf8');
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(raw, {headers: {'content-type': 'application/json'}})));
      const data = await (await getLoader())(entry.video_id);
      expect(data, `${folder}/${entry.video_id}`).toEqual(JSON.parse(raw));
      expect(data && key in data).toBe(true);
    }
  }
});
