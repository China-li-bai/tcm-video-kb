// @vitest-environment jsdom
// Real citation component + router + WatchPage effects. No YouTube/HTTP network.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { CiteLinks } from '../panel/format';
import { WatchPage } from '../pages/listen/WatchPage';
import type { Citation } from '../types';
const json=(body:unknown)=>new Response(JSON.stringify(body),{headers:{'content-type':'application/json'}});
beforeEach(()=>{
 localStorage.clear();
 Object.defineProperty(Element.prototype,'scrollIntoView',{configurable:true,writable:true,value:vi.fn()});
 vi.stubGlobal('IntersectionObserver',class{observe(){}disconnect(){}unobserve(){}});
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{
  const url=String(input);
  if(url==='/transcripts/shl-001.json')return json({video_id:'shl-001',segments:[{seq:0,start_s:125,end_s:130,text:'测试原句'}]});
  const match=/^\/(knowledge|entities)\/(shl-001|zj-083)\.json$/.exec(url);
  if(!match)throw new Error(`Unexpected network request: ${url}`);
  return json({video_id:match[2],[match[1]==='knowledge'?'points':'mentions']:[]});
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function Location(){const l=useLocation();return <output data-testid="route">{l.pathname}{l.search}</output>;}
function open(cite:Citation){return render(<MemoryRouter><Location/><Routes><Route path="/" element={<CiteLinks cite={cite}/>}/><Route path="/watch/:videoId" element={<WatchPage/>}/></Routes></MemoryRouter>);}
it('covered citation ignores hostile t_url and actually routes to the existing player request',async()=>{
 open({video_id:'shl-001',start_s:125.99,t_url:'https://evil.test',youtube_t_url:'javascript:alert(1)'});
 const link=screen.getByRole('link',{name:/听原讲/});
 expect(link.getAttribute('href')).toBe('/watch/shl-001?t=125');
 expect(screen.getByText(/已有句稿/)).toBeTruthy();
 expect(screen.getByRole('link',{name:/YouTube/}).getAttribute('href')).toMatch(/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]+&t=125s$/);
 fireEvent.click(link);
 expect(screen.getByTestId('route').textContent).toBe('/watch/shl-001?t=125');
 expect(await screen.findByText('测试原句')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'点这里听'}));
 expect(new URL(document.querySelector('iframe')!.src).searchParams.get('start')).toBe('125');
 expect(screen.queryByText(/正在播放|已播放|实时跟读|28%/)).toBeNull();
});
it('an uncovered but catalogued lecture remains listenable without claiming a transcript',async()=>{
 open({video_id:'zj-083',start_s:163.36});
 expect(screen.getByText(/暂未公开句稿/)).toBeTruthy();
 fireEvent.click(screen.getByRole('link',{name:/听原讲/}));
 expect(screen.getByTestId('route').textContent).toBe('/watch/zj-083?t=163');
 await waitFor(()=>expect(document.querySelector('.listen-stage-watch')).toBeTruthy());
 expect(screen.queryByText('测试原句')).toBeNull();
 expect(vi.mocked(fetch).mock.calls.some(([u])=>String(u).startsWith('/transcripts/zj-083'))).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'点这里听'}));
 expect(new URL(document.querySelector('iframe')!.src).searchParams.get('start')).toBe('163');
});
it.each([{}, {video_id:'shl-999',start_s:0}, {video_id:'../../evil',t_url:'//evil.test'}, {video_id:'shl-001',start_s:NaN}])('incomplete/invalid citation never gets an invented station link %#',(cite)=>{
 open(cite);
 expect(screen.queryByRole('link',{name:/听原讲/})).toBeNull();
 expect(screen.getByText(/出处信息不完整|时间信息无效/)).toBeTruthy();
 expect(document.querySelector('a[href^="javascript:"],a[href^="//"]')).toBeNull();
});
it('a legacy YouTube-only source gets a safe backup, not an invented video identity',()=>{
 open({youtube_t_url:'https://youtu.be/W-z7WGZXmp8?t=3',start_s:3});
 expect(screen.queryByRole('link',{name:/听原讲/})).toBeNull();
 expect(screen.getByRole('link',{name:/YouTube/}).getAttribute('href')).toBe('https://www.youtube.com/watch?v=W-z7WGZXmp8&t=3s');
});
it('duplicate citations resolve consistently and never mutate their source',()=>{
 const cite={video_id:'shl-001',start_s:0,t_url:'https://evil.test'};
 const before=JSON.stringify(cite);
 render(<MemoryRouter><CiteLinks cite={cite}/><CiteLinks cite={cite}/></MemoryRouter>);
 expect(screen.getAllByRole('link',{name:/听原讲/}).map(a=>a.getAttribute('href'))).toEqual(['/watch/shl-001','/watch/shl-001']);
 expect(JSON.stringify(cite)).toBe(before);
});
it('PathsPage cards and compare view both use safe, coverage-aware citations from the actual API adapter',async()=>{
 const {PathsPage}=await import('../pages/PathsPage');
 vi.mocked(fetch).mockImplementation(async(input)=>{
  expect(String(input)).toMatch(/^\/graph\/paths\?focus=/);
  const card={subj_id:'pulse.test',obj_id:'syndrome.test',label:'测试脉',category:'pulse',pred:'indicates',kp_id:'pr5.evidence',review_status:'candidate',video_id:'zj-083',start_s:163.36,t_url:'https://evil.test',youtube_t_url:'javascript:alert(1)',evidence_quote:'PR5路径出处证据'};
  return json({focus:'syndrome.pr5_test',disclaimer:'非诊疗',equal_weight:true,tracks:[{syndrome_id:'syndrome.test',label:'PR5测试证',treats:[],cards:[card]}],held:[]});
 });
 render(<MemoryRouter><PathsPage/></MemoryRouter>);
 await screen.findByText('PR5路径出处证据',{exact:false});
 const assertLinks=()=>{
  expect(screen.getAllByRole('link',{name:/听原讲/}).every(a=>a.getAttribute('href')==='/watch/zj-083?t=163')).toBe(true);
  expect(screen.getAllByText(/暂未公开句稿/).length).toBeGreaterThan(0);
  expect(document.querySelector('a[href^="https://evil"],a[href^="javascript:"]')).toBeNull();
 };
 assertLinks();
 fireEvent.click(screen.getByRole('button',{name:'对比表'}));
 assertLinks();
});
it('saved quote replay uses the same zero-time canonical route',async()=>{
 const {StashPage}=await import('../pages/listen/StashPage');
 const {saveStashItem}=await import('./stash');
 saveStashItem({videoId:'shl-001',title:'测试',text:'PR5已存原句',t:0});
 render(<MemoryRouter><StashPage/></MemoryRouter>);
 expect(screen.getByRole('link',{name:'听原讲'}).getAttribute('href')).toBe('/watch/shl-001');
});
it('recall replay clamps finite negative legacy positions using the single site builder',async()=>{
 const {RecallPage}=await import('../pages/listen/RecallPage');
 const {saveStashItem}=await import('./stash');
 const item=saveStashItem({videoId:'shl-001',title:'测试',text:'PR5待回想原句',t:-1.2});
 render(<MemoryRouter initialEntries={[`/recall/${item.id}`]}><Routes><Route path="/recall/:itemId" element={<RecallPage/>}/></Routes></MemoryRouter>);
 expect(screen.getByRole('link',{name:'听原讲'}).getAttribute('href')).toBe('/watch/shl-001');
});
it('resume does not construct a station URL from an invalid stored source identity',async()=>{
 const {ListenHomePage}=await import('../pages/listen/ListenHomePage');
 const {setLastWatch}=await import('./stash');
 setLastWatch({videoId:'../evil',title:'未知讲次',chapterTitle:'原位置',t:20,updatedAt:new Date().toISOString()});
 render(<MemoryRouter><ListenHomePage/></MemoryRouter>);
 expect(document.querySelector('a[href*="evil"]')).toBeNull();
 expect(screen.getByText(/上次出处信息不完整/)).toBeTruthy();
});
it('the real graph detail panel does not print NaN/Infinity as citation time metadata',async()=>{
 const {DetailPanel}=await import('../panel/DetailPanel');
 const id='formula.pr5_test';
 const citations=[NaN,Infinity,-Infinity].map(start_s=>({video_id:'shl-001',start_s}));
 render(<MemoryRouter><DetailPanel subgraph={{focus:id,disclaimer:'非诊疗',nodes:[{id,label:'PR5测试节点',category:'formula',citations}],edges:[],held:[]}} selection={{kind:'node',id}} onClear={()=>{}}/></MemoryRouter>);
 expect(document.body.textContent).not.toMatch(/NaN|Infinity/);
 expect(screen.queryByRole('link',{name:/听原讲/})).toBeNull();
 expect(screen.getAllByText(/时间信息无效/)).toHaveLength(3);
});
