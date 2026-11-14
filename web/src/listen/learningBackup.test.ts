import {describe,expect,it} from 'vitest';
import {parseLearningBackup,createLearningBackup,previewLearningImport,confirmLearningImport,readImportRecovery,restoreImportRecovery,keepCurrentRecovery,MAX_BACKUP_BYTES,RECOVERY_KEY} from './learningBackup';
const S='renji.listen.stash.v1',L='renji.listen.lastWatch.v1';
const item=(id='a',text='合成原句')=>({id,videoId:'shl-001',title:'',text,t:0,savedAt:'2026-11-09'});
const last={videoId:'shl-001',title:'请求位置',t:125.8,chapterId:'shl-001.c01',chapterTitle:'第一章',updatedAt:'2026-11-09T00:00:00Z'};
const state=(stash:unknown[]=[item()],watch:unknown=last)=>({schema:'listen-state/1',[S]:stash,[L]:watch});
class Store {
 data=new Map<string,string>();writes:string[]=[];reads:string[]=[];
 fault:((key:string,value:string|null)=>boolean)=()=>false;
 getItem(key:string){this.reads.push(key);return this.data.get(key)??null;}
 setItem(key:string,value:string){this.writes.push(key);if(this.fault(key,value))throw new Error('synthetic storage fault');this.data.set(key,value);}
 removeItem(key:string){this.writes.push(key);if(this.fault(key,null))throw new Error('synthetic storage fault');this.data.delete(key);}
}
const parsed=(stash:unknown[]=[item()],watch:unknown=last)=>parseLearningBackup(JSON.stringify(state(stash,watch)));
describe('versioned allowlisted learning backup',()=>{
 it('roundtrips actual v1 keys, Unicode, zero/fractional and optional historical fields',()=>{
  const s=new Store();const old={id:'legacy',videoId:'jgy-015',title:'旧记录',text:'0秒与小数；不是已播放',savedAt:'2026-11-09'};
  s.data.set(S,JSON.stringify([old,item()]));s.data.set(L,JSON.stringify(last));s.data.set('private.token','NEVER');
  const text=createLearningBackup(s);expect(parseLearningBackup(text)).toEqual(state([old,item()]));expect(text).not.toContain('NEVER');
  expect(s.reads).toEqual([S,L]);
 });
 it('exports absent storage as an explicit empty state, not by enumerating other keys',()=>expect(JSON.parse(createLearningBackup(new Store()))).toEqual(state([],null)));
 it.each([
  ['malformed','{'],['HTML','<html>SPA</html>'],['null','null'],['array','[]'],['unversioned',JSON.stringify({[S]:[]})],
  ['future',JSON.stringify({...state(),schema:'listen-state/2'})],
  ['extra URL',JSON.stringify({...state(),url:'javascript:alert(1)'})],
  ['prototype root','{"schema":"listen-state/1","__proto__":{"polluted":true},"'+S+'":[],"'+L+'":null}'],
  ['constructor',JSON.stringify(state([{...item(),constructor:{prototype:{polluted:true}}}]))],
  ['record URL',JSON.stringify(state([{...item(),t_url:'https://evil.example/'}]))],
  ['path injection',JSON.stringify(state([{...item(),videoId:'../evil'}]))],
  ['unknown video',JSON.stringify(state([{...item(),videoId:'shl-999'}]))],
  ['unsafe recall id',JSON.stringify(state([{...item(),id:'a?next=https://evil.example'}]))],
  ['bad timestamp',JSON.stringify(state([{...item(),savedAt:'not-a-date'}]))],
  ['negative',JSON.stringify(state([{...item(),t:-1}]))],['null seconds',JSON.stringify(state([{...item(),t:null}]))],
  ['overflow seconds','{"schema":"listen-state/1","'+S+'":[],"'+L+'":{"videoId":"shl-001","title":"x","t":1e999,"updatedAt":"2026-11-09"}}'],
  ['cross-lecture chapter',JSON.stringify(state([], {...last,chapterId:'jgy-001.c01'}))],
  ['object text',JSON.stringify(state([{...item(),text:{html:'<script>'}}]))],
  ['missing field',JSON.stringify(state([{id:'a',videoId:'shl-001',text:'x'}]))],
  ['long text',JSON.stringify(state([{...item(),text:'x'.repeat(10001)}]))],
  ['overcount',JSON.stringify(state(Array.from({length:201},(_,i)=>item(`i${i}`,`text${i}`))))],
 ])('rejects %s without prototype mutation',(_name,text)=>{expect(()=>parseLearningBackup(text)).toThrow();expect(({} as {polluted?:unknown}).polluted).toBeUndefined();});
 it('checks UTF-8 bytes, not just JS string length',()=>{expect(()=>parseLearningBackup('汉'.repeat(Math.floor(MAX_BACKUP_BYTES/3)+1))).toThrow(/2 MiB/);});
 it('treats URL-like quoted text as inert text, never as a route or executable URL',()=>expect(parsed([item('safe','javascript:alert(1) <script>')])[S][0].text).toBe('javascript:alert(1) <script>'));
 it.each(['{','null','{}','[null]','[{"id":"bad"}]'])('refuses damaged local stash %s instead of silently exporting empty',raw=>{const s=new Store();s.data.set(S,raw);expect(()=>createLearningBackup(s)).toThrow(/本机.*损坏/);expect(s.writes).toEqual([]);});
 it('reports denied reads and never accesses unrelated storage',()=>{const s=new Store();s.getItem=()=>{throw new Error('denied');};expect(()=>createLearningBackup(s)).toThrow(/读取/);expect(s.writes).toEqual([]);});
});
describe('existing-first merge and durable failure boundary',()=>{
 it('deduplicates video+text and colliding IDs, retains existing order/values and last request even when file is newer',()=>{
  const s=new Store();s.data.set(S,JSON.stringify([item()]));s.data.set(L,JSON.stringify(last));
  const incoming=[{...item('b'),t:50},item('a','ID collision'),item('c','new'),item('d','new')];
  const plan=previewLearningImport(parsed(incoming,{...last,videoId:'jgy-001',chapterId:'jgy-001.c01',t:999}),s);
  expect(plan.state[S]).toEqual([item(),item('c','new')]);expect(plan.state[L]).toEqual(last);
  expect(plan.added).toBe(1);expect(plan.conflicts).toBe(3);expect(plan.overflow).toBe(0);expect(s.writes).toEqual([]);
 });
 it('fills only remaining slots, without truncating any of 199 existing records',()=>{
  const s=new Store();const existing=Array.from({length:199},(_,i)=>item(`old${i}`,`old ${i}`));s.data.set(S,JSON.stringify(existing));
  const plan=previewLearningImport(parsed([item('new1','new1'),item('new2','new2')],null),s);
  expect(plan.state[S]).toEqual([...existing,item('new1','new1')]);expect(plan.overflow).toBe(1);confirmLearningImport(plan,s);
  expect(JSON.parse(s.getItem(S)!)).toHaveLength(200);
 });
 it('empty incoming cannot clear existing records, and a no-op makes zero writes',()=>{
  const s=new Store();s.data.set(S,JSON.stringify([item()]));s.data.set(L,JSON.stringify(last));
  const before=new Map(s.data);confirmLearningImport(previewLearningImport(parsed([],null),s),s);expect(s.data).toEqual(before);expect(s.writes).toEqual([]);
 });
 it('confirmation uses preview snapshot and rejects later edits',()=>{
  const s=new Store(),plan=previewLearningImport(parsed(),s);s.data.set(S,'[]');expect(()=>confirmLearningImport(plan,s)).toThrow(/变化|重新预览/);expect(s.writes).toEqual([]);
 });
 it('stores only learning keys and removes recovery after a successful import',()=>{
  const s=new Store();s.data.set('unrelated','KEEP');confirmLearningImport(previewLearningImport(parsed(),s),s);
  expect(s.getItem('unrelated')).toBe('KEEP');expect(s.getItem(RECOVERY_KEY)).toBeNull();expect(s.writes.every(k=>[S,L,RECOVERY_KEY].includes(k))).toBe(true);
 });
 it('journal/quota rejection happens before any original data write',()=>{
  const s=new Store();const before=new Map(s.data);const plan=previewLearningImport(parsed(),s);s.fault=k=>k===RECOVERY_KEY;
  expect(()=>confirmLearningImport(plan,s)).toThrow(/失败/);expect(s.data).toEqual(before);expect(s.writes).toEqual([RECOVERY_KEY]);
 });
 it('second write failure rolls back exact bytes and absent keys, without touching unknown keys',()=>{
  const s=new Store();s.data.set(S,'[\n'+JSON.stringify(item('old','old'))+'\n]');s.data.set('unrelated','KEEP');const before=new Map(s.data);
  const plan=previewLearningImport(parsed(),s);s.fault=k=>k===L;expect(()=>confirmLearningImport(plan,s)).toThrow(/失败.*已恢复/);expect(s.data).toEqual(before);
 });
 it('failed rollback preserves durable originals across reload, blocks another import, and can restore later',()=>{
  const s=new Store();const original=JSON.stringify([item('old','old')]);s.data.set(S,original);const plan=previewLearningImport(parsed(),s);
  s.fault=(k,v)=>k===L||(k===S&&v===original);expect(()=>confirmLearningImport(plan,s)).toThrow(/恢复.*未完成/);
  const reloaded=readImportRecovery(s)!;expect(reloaded.before[S]).toBe(original);expect(()=>previewLearningImport(parsed(),s)).toThrow(/恢复/);
  s.fault=()=>false;restoreImportRecovery(reloaded,s);expect(s.getItem(S)).toBe(original);expect(s.getItem(L)).toBeNull();expect(readImportRecovery(s)).toBeNull();
 });
 it('cleanup failure cannot erase the original recovery copy; explicit keep-current only clears that key',()=>{
  const s=new Store();const plan=previewLearningImport(parsed(),s);s.fault=(k,v)=>k===RECOVERY_KEY&&v===null;
  expect(()=>confirmLearningImport(plan,s)).toThrow();expect(readImportRecovery(s)).not.toBeNull();s.fault=()=>false;
  const current=new Map(s.data);keepCurrentRecovery(readImportRecovery(s)!,s);current.delete(RECOVERY_KEY);expect(s.data).toEqual(current);
 });
 it('recovery refuses to overwrite records changed since the interrupted import',()=>{
  const s=new Store(),plan=previewLearningImport(parsed(),s);s.fault=k=>k===L||k===S&&s.data.has(S);
  expect(()=>confirmLearningImport(plan,s)).toThrow();s.fault=()=>false;const r=readImportRecovery(s)!;
  s.data.set(S,JSON.stringify([item('later','later')]));const before=new Map(s.data);expect(()=>restoreImportRecovery(r,s)).toThrow(/变化/);expect(s.data).toEqual(before);
 });
 it('bad recovery journal is not removed or trusted',()=>{
  const s=new Store();s.data.set(RECOVERY_KEY,'{"schema":"bad","before":{}}');expect(()=>readImportRecovery(s)).toThrow(/恢复/);expect(s.writes).toEqual([]);
 });
});
it.each(['2026-02-30','2026-11-09T24:00:00Z'])('rejects invalid calendar/clock timestamp %s rather than Date.parse rollover',savedAt=>{
 expect(()=>parseLearningBackup(JSON.stringify(state([{...item(),savedAt}])))).toThrow(/日期/);
});
it('accepts exactly the UTF-8 size limit and rejects one byte above',()=>{
 const text=JSON.stringify(state([],null));const limit=text+' '.repeat(MAX_BACKUP_BYTES-new TextEncoder().encode(text).byteLength);
 expect(parseLearningBackup(limit)).toEqual(state([],null));expect(()=>parseLearningBackup(limit+' ')).toThrow(/2 MiB/);
});
it('keeps a valid leap day and explicit timezone legacy date byte-for-byte',()=>{
 const s=new Store();s.data.set(S,JSON.stringify([{...item(),savedAt:'2024-02-29'}]));s.data.set(L,JSON.stringify({...last,updatedAt:'2026-11-09T08:00:00+08:00'}));
 expect(parseLearningBackup(createLearningBackup(s))[L]?.updatedAt).toBe('2026-11-09T08:00:00+08:00');
});
it('a failed first data write preserves originals and removes the pending recovery journal',()=>{
 const s=new Store(),plan=previewLearningImport(parsed(),s);s.fault=k=>k===S;
 expect(()=>confirmLearningImport(plan,s)).toThrow(/失败.*已恢复/);expect([...s.data]).toEqual([]);
});
it('a second restore attempt succeeds after a restore-time permission failure, without losing the journal',()=>{
 const s=new Store(),plan=previewLearningImport(parsed(),s);s.fault=k=>k===L||k===S&&s.data.has(S);
 expect(()=>confirmLearningImport(plan,s)).toThrow();s.fault=k=>k===S;const r=readImportRecovery(s)!;
 expect(()=>restoreImportRecovery(r,s)).toThrow(/恢复.*未完成/);expect(readImportRecovery(s)).not.toBeNull();
 s.fault=()=>false;restoreImportRecovery(readImportRecovery(s)!,s);expect([...s.data]).toEqual([]);
});
it('existing malformed lastWatch is not replaced by a valid incoming one',()=>{
 const s=new Store();s.data.set(L,'{"videoId":"shl-001","t":null}');const before=new Map(s.data);
 expect(()=>previewLearningImport(parsed(),s)).toThrow(/本机.*损坏/);expect(s.data).toEqual(before);expect(s.writes).toEqual([]);
});
