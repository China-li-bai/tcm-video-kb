import { expect, it } from 'vitest';
import { pickClaimsNear, type KnowledgePoint } from './knowledgePoints';
import { pickChipsNear, type EntityMention } from './entities';
import { chapterAsUtterances } from './chapters';
import type { Chapter } from './types';

const point = (id:string,start:number,end:number,confidence=0.8):KnowledgePoint => ({kp_id:id,video_id:'shl-001',type:'claim',statement:id,evidence_quote:'证据',start_s:start,end_s:end,confidence});
const mention = (id:string,type:string,start:number,end:number):EntityMention => ({entity_id:id,label:id,type,start_s:start,end_s:end});
const chapter = (summary:string,start=10.75,end=100.75):Chapter => ({chapter_id:'fixture.c01',video_id:'shl-001',level:1,parent_id:null,seq:1,title:'章节标题',summary,start_s:start,end_s:end});

it('claims: empty, exact 45-second interval distance, fractional outside and invalid query time are honest', () => {
  expect(pickClaimsNear([],100)).toEqual([]);
  const atBoundary = point('boundary',145,150);
  const beyond = point('beyond',145.001,151);
  expect(pickClaimsNear([beyond,atBoundary],100)).toEqual([atBoundary]);
  expect(pickClaimsNear([point('before',40,55)],100)).toHaveLength(1);
  expect(pickClaimsNear([point('before',40,54.999)],100)).toEqual([]);
  expect(pickClaimsNear([atBoundary],Number.NaN)).toEqual([]);
  expect(pickClaimsNear([point('zero',0,1)],-1)).toHaveLength(1);
});
it('claims: overlap then distance, confidence/start tie-breaks, dedupe and cap without mutating source', () => {
  const low = point('low',99,101,0.6);
  const high = point('high',98,102,0.9);
  const early = point('early',97,103,0.9);
  const near = point('near',103,104,1);
  const source = [near,low,high,early,{...high}];
  const snapshot = structuredClone(source);
  expect(pickClaimsNear(source,100).map(p=>p.kp_id)).toEqual(['early','high','low']);
  expect(pickClaimsNear(source,100,{nearWindowS:0,max:10}).map(p=>p.kp_id)).toEqual(['early','high','low']);
  expect(pickClaimsNear(source,100,{nearWindowS:2,max:10}).some(p=>p.kp_id==='near')).toBe(false);
  expect(source).toEqual(snapshot);
});
it('claims: max is a finite whole-item cap, including zero and invalid caps', () => {
  const rows = [point('a',1,2),point('b',1,2),point('c',1,2)];
  for (const max of [0,-1,Number.NaN,Infinity]) expect(pickClaimsNear(rows,1,{max})).toEqual([]);
  expect(pickClaimsNear(rows,1,{max:1.9})).toHaveLength(1);
});
it('chips: empty, interval-distance <=6 seconds, fractional outside and default/minimum sentence windows', () => {
  expect(pickChipsNear([],100,110)).toEqual([]);
  const before=mention('before','herb',90,94), after=mention('after','herb',116,117);
  expect(pickChipsNear([before,after,mention('far','formula',116.001,118)],100,110)).toEqual([before,after]);
  expect(pickChipsNear([mention('default','formula',110,111)],100)).toHaveLength(1); // hi=104, distance=6
  expect(pickChipsNear([mention('half','formula',106.5,107)],100,99)).toHaveLength(1); // hi=100.5
  expect(pickChipsNear([before],Number.NaN)).toEqual([]);
});
it('chips: overlap precedes nearby, type tie-breaks, repeated entity is one chip and source order is untouched', () => {
  const source = [mention('herb.a','herb',101,104),mention('formula.a','formula',102,105),mention('formula.a','formula',103,106),mention('syndrome.a','syndrome',102,105),mention('symptom.a','symptom',102,105),mention('near','formula',111,112)];
  const snapshot=structuredClone(source);
  expect(pickChipsNear(source,100,110).map(m=>m.entity_id)).toEqual(['formula.a','syndrome.a','symptom.a']);
  expect(pickChipsNear(source,100,110,{max:10}).map(m=>m.entity_id)).toEqual(['formula.a','syndrome.a','symptom.a','herb.a','near']);
  expect(source).toEqual(snapshot);
});
it('chips: max is a finite whole-item cap, including zero and invalid caps', () => {
  const rows=[mention('a','formula',1,2),mention('b','herb',1,2)];
  for (const max of [0,-1,Number.NaN,Infinity]) expect(pickChipsNear(rows,1,undefined,{max})).toEqual([]);
  expect(pickChipsNear(rows,1,undefined,{max:1.9})).toHaveLength(1);
});
it('summary interpolation splits punctuation, removes blank pieces, keeps monotonic approximate whole seconds', () => {
  const ch=chapter('第一段； \n第二段。第三段！');
  expect(chapterAsUtterances(ch)).toEqual([{t:10,text:'第一段。'},{t:40,text:'第二段。'},{t:70,text:'第三段。'}]);
});
it('summary interpolation never invents positions outside a short valid chapter window', () => {
  const ch=chapter('第一段；第二段；第三段',10.75,15.75);
  const rows=chapterAsUtterances(ch);
  expect(rows).toHaveLength(3);
  expect(rows.every(r=>r.t>=Math.floor(ch.start_s)&&r.t<ch.end_s)).toBe(true);
  expect(rows.map(r=>r.t)).toEqual([10,12,14]);
});
it('empty summary is the title at its source start, not fabricated raw sentences', () => {
  const ch=chapter(' ；。\n');
  expect(chapterAsUtterances(ch)).toEqual([{t:ch.start_s,text:ch.title}]);
});
