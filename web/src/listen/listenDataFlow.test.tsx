// @vitest-environment jsdom
// No external subresources in jsdom. HTTP fixtures exercise the real loaders, not mocked search/pickers.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { ComponentType } from 'react';
let SearchPage:ComponentType, WatchPage:ComponentType;
let release:()=>void;
let hold=false;
let mode:'near'|'far'|'empty'='near';
let pending:Promise<void>;
const json=(body:unknown)=>new Response(JSON.stringify(body),{headers:{'content-type':'application/json'}});
beforeEach(async()=>{
  vi.resetModules();localStorage.clear();hold=false;mode='near';
  pending=new Promise<void>(resolve=>{release=resolve;});
  Object.defineProperty(Element.prototype,'scrollIntoView',{configurable:true,writable:true,value:vi.fn()});
  vi.stubGlobal('IntersectionObserver',class{observe(){}disconnect(){}unobserve(){}});
  vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input),match=/^\/(transcripts|knowledge|entities)\/([\w-]+)\.json$/.exec(url);
    if(!match)throw new Error(`No live network fallback: ${url}`);
    const [,layer,id]=match;
    if(layer==='transcripts'){
      if(hold)await pending;
      const segments=id==='shl-001'?[{seq:0,start_s:125.8,end_s:130,text:'PR4Alpha 原讲句'},{seq:1,start_s:140.25,end_s:145,text:'PR4Beta 原讲句'}]:[{seq:0,start_s:125.8,end_s:130,text:'B集句子'}];
      return json({video_id:id,segments});
    }
    if(layer==='knowledge'){
      const tag=id==='shl-001'?'A':'B';
      const point=(suffix:string,start:number,statement:string)=>({kp_id:`${id}.${suffix}`,video_id:id,type:'concept_definition',statement,evidence_quote:`证据${tag}片`,start_s:start,end_s:start+3,confidence:0.9});
      const far=point('kpFar',190,'远处不该显示');
      const points=mode==='empty'?[]:mode==='far'?[far]:[point('kpNear',126.6,`${tag}集附近主张`),far];
      return json({video_id:id,points});
    }
    return json({video_id:id,mentions:[
      {entity_id:'formula.gui_zhi_tang',label:'桂枝汤测试芯片',type:'formula',start_s:125.8,end_s:129},
      {entity_id:'formula.gui_zhi_tang',label:'桂枝汤测试芯片',type:'formula',start_s:126.8,end_s:129},
    ]});
  }));
  ({SearchPage}=await import('../pages/listen/SearchPage'));
  ({WatchPage}=await import('../pages/listen/WatchPage'));
});
afterEach(()=>{
  cleanup();
  expect(vi.mocked(fetch).mock.calls.every(([url])=>/^\/(transcripts|knowledge|entities)\/[\w-]+\.json$/.test(String(url)))).toBe(true);
  vi.unstubAllGlobals();
});
function Location(){const l=useLocation();return <output data-testid="route">{l.pathname}{l.search}</output>;}
function open(path='/search'){
  return render(<MemoryRouter initialEntries={[path]}><Link to="/watch/jgy-001?t=125">换到B集</Link><Location/><Routes><Route path="/search" element={<SearchPage/>}/><Route path="/watch/:videoId" element={<WatchPage/>}/></Routes></MemoryRouter>);
}
function submit(q:string){const input=screen.getByRole('textbox');fireEvent.change(input,{target:{value:q}});fireEvent.submit(input.closest('form')!);}
async function ask(){
  const row=(await screen.findByText('PR4Alpha 原讲句')).closest('[role="button"]')!;
  fireEvent.click(row);
  fireEvent.click(screen.getByRole('button',{name:'这句还能做什么'}));
  fireEvent.click(screen.getByRole('button',{name:'问这句'}));
  return screen.getByRole('dialog',{name:'对照原讲主张'});
}
it('search blank/no-match/reset UI is driven by actual search and does not fabricate results',async()=>{
  open();
  expect(fetch).not.toHaveBeenCalled();
  submit('   ');
  expect(fetch).not.toHaveBeenCalled();
  submit('PR4-NONEXISTENT-QUERY');
  expect(await screen.findByRole('heading',{name:'暂时找不到可靠出处'})).toBeTruthy();
  expect(document.querySelector('.hit-card')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'换说法'}));
  expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('');
  expect(screen.getByTestId('route').textContent).toBe('/search');
  expect(screen.queryByRole('heading',{name:'暂时找不到可靠出处'})).toBeNull();
});
it('a newer query wins when both searches share delayed transcript fetches',async()=>{
  hold=true;open('/search?q=PR4Alpha');
  expect(screen.getByText('正在翻原文句子…')).toBeTruthy();
  submit('PR4Beta');
  await act(async()=>{release();});
  expect(await screen.findByText('PR4Beta 原讲句')).toBeTruthy();
  expect(screen.queryByText('PR4Alpha 原讲句')).toBeNull();
  expect(screen.getByTestId('route').textContent).toBe('/search?q=PR4Beta');
});
it('a real quote-search hit navigates into WatchPage with its existing whole-second location and source',async()=>{
  open('/search?q=PR4Alpha');
  const snippet=await screen.findByText('PR4Alpha 原讲句');
  fireEvent.click(within(snippet.closest('article')!).getByRole('link',{name:'从 02:05 听'}));
  expect(screen.getByTestId('route').textContent).toBe('/watch/shl-001?t=125');
  fireEvent.click(await screen.findByRole('button',{name:'点这里听'}));
  expect(new URL(document.querySelector('iframe')!.src).searchParams.get('start')).toBe('125');
  expect(JSON.parse(localStorage.getItem('renji.listen.lastWatch.v1')!).t).toBe(125);
});
it('WatchPage derives deduplicated chips and nearby claim options from loaded rows; selecting evidence is not human review',async()=>{
  open('/watch/shl-001?t=125');
  await screen.findByText('桂枝汤测试芯片');
  expect(document.querySelectorAll('.entity-chip')).toHaveLength(1);
  const dialog=await ask();
  expect(await within(dialog).findByText('A集附近主张')).toBeTruthy();
  expect(within(dialog).queryByText('远处不该显示')).toBeNull();
  fireEvent.click(within(dialog).getByRole('listitem'));
  expect(within(dialog).getByText('「证据A片」')).toBeTruthy();
  expect(within(dialog).queryByText(/核对过/)).toBeNull();
  fireEvent.click(within(dialog).getByRole('button',{name:'听这段主张的开头'}));
  expect(new URL(document.querySelector('iframe')!.src).searchParams.get('start')).toBe('126');
  expect(screen.queryByRole('dialog')).toBeNull();
});
it.each(['empty','far'] as const)('WatchPage ask has a genuine empty state for %s data, not invented options',async(kind)=>{
  mode=kind;open('/watch/shl-001?t=125');
  const dialog=await ask();
  expect(await within(dialog).findByText('这段附近暂时没有收录主张')).toBeTruthy();
  expect(within(dialog).queryAllByRole('listitem')).toHaveLength(0);
  expect(within(dialog).queryByText('这集的知识点暂时没能打开')).toBeNull();
});
it('an open ask sheet changes video-scoped source data without retaining the previous lecture claim/evidence',async()=>{
  open('/watch/shl-001?t=125');
  const dialog=await ask();
  fireEvent.click(await within(dialog).findByRole('listitem'));
  expect(within(dialog).getByText('「证据A片」')).toBeTruthy();
  fireEvent.click(screen.getByRole('link',{name:'换到B集'}));
  expect(await screen.findByText('B集附近主张')).toBeTruthy();
  await waitFor(()=>expect(screen.queryByText('A集附近主张')).toBeNull());
  expect(screen.queryByText('「证据A片」')).toBeNull();
  fireEvent.click(within(screen.getByRole('dialog',{name:'对照原讲主张'})).getByRole('listitem'));
  expect(screen.getByText('「证据B片」')).toBeTruthy();
});
