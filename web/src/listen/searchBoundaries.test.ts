import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { getAllLectures } from './lectures';
import { TRANSCRIPT_VIDEO_IDS } from './transcriptCoverage';

beforeEach(()=>vi.resetModules());
afterEach(()=>vi.unstubAllGlobals());
it('blank catalog/quote queries and absent catalog matches remain empty, with no downloads for blank queries',async()=>{
  const fetch=vi.fn(()=>{throw new Error('No fetch for blank input');});vi.stubGlobal('fetch',fetch);
  const {searchCatalog,searchQuotes}=await import('./search');
  expect(searchCatalog(' \n ')).toEqual([]);
  expect(searchCatalog('NONEXISTENT-PR4-FIXTURE')).toEqual([]);
  expect(await searchQuotes(' \n ')).toEqual([]);
  expect(fetch).not.toHaveBeenCalled();
});
it('catalog matching trims/case-folds, prioritizes chapter hits and does not duplicate their lecture cards',async()=>{
  const {searchCatalog}=await import('./search');
  expect(searchCatalog(' SHL-001 ')).toEqual(searchCatalog('shl-001'));
  const hits=searchCatalog('桂枝');
  expect(hits.length).toBeGreaterThan(0);
  const chapterIds=new Set(hits.filter(h=>h.kind==='chapter').map(h=>h.lecture.id));
  expect(hits.filter(h=>h.kind==='lecture').every(h=>!chapterIds.has(h.lecture.id))).toBe(true);
  expect(hits.filter(h=>h.kind==='chapter').length).toBeLessThanOrEqual(40);
  expect(hits.filter(h=>h.kind==='lecture').length).toBeLessThanOrEqual(20);
});
it('quote search uses only manifest coverage, keeps catalog/time order despite reverse arrival and bounds results',async()=>{
  const covered=new Set(TRANSCRIPT_VIDEO_IDS);
  const lectures=getAllLectures().filter(l=>covered.has(l.id));
  const [first,second]=lectures;
  let release!:()=>void;
  const barrier=new Promise<void>(resolve=>{release=resolve;});
  const fetch=vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input), match=/^\/transcripts\/([\w-]+)\.json$/.exec(url);
    if(!match)throw new Error(`Unexpected external path ${url}`);
    const id=match[1];
    if(id===first.id)await barrier;
    else if(id===second.id)release();
    else return new Response('{}',{status:404,headers:{'content-type':'application/json'}});
    const rows=id===first.id?[{seq:0,start_s:20.9,end_s:23,text:'FixtureToken later'},{seq:1,start_s:30.1,end_s:35,text:'FIXTURETOKEN last'}]:[{seq:0,start_s:1.5,end_s:3,text:'FixtureToken other lecture'}];
    return new Response(JSON.stringify({video_id:id,segments:rows}),{headers:{'content-type':'application/json'}});
  });
  vi.stubGlobal('fetch',fetch);
  const {searchQuotes}=await import('./search');
  const hits=await searchQuotes(' fixtureTOKEN ');
  expect(hits.map(h=>[h.lecture.id,h.startS])).toEqual([[first.id,20.9],[first.id,30.1],[second.id,1.5]]);
  expect(hits.map(h=>h.href)).toEqual([`/watch/${first.id}?t=20`,`/watch/${first.id}?t=30`,`/watch/${second.id}?t=1`]);
  expect(new Set(hits.map(h=>h.key)).size).toBe(3);
  expect(await searchQuotes('FixtureToken',2)).toEqual(hits.slice(0,2));
  expect(await searchQuotes('no-fixture-match')).toEqual([]);
  expect(fetch).toHaveBeenCalledTimes(TRANSCRIPT_VIDEO_IDS.length);
  expect(new Set(fetch.mock.calls.map(([url])=>String(url)))).toEqual(new Set(TRANSCRIPT_VIDEO_IDS.map(id=>`/transcripts/${id}.json`)));
});
