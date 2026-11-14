// @vitest-environment jsdom
// Real components, FileReader, storage and merge logic; only download URL/click are browser substitutes.
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {StashPage} from '../pages/listen/StashPage';
const STASH='renji.listen.stash.v1', LAST='renji.listen.lastWatch.v1';
const item=(id='new',text='合成学习原句')=>({id,videoId:'shl-001',title:'测试',text,t:125.8,savedAt:'2026-11-09'});
const documentOf=(items=[item()])=>JSON.stringify({schema:'listen-state/1',[STASH]:items,[LAST]:{videoId:'jgy-001',title:'合成请求位置',t:0,updatedAt:'2026-11-09'}});
let downloaded:Blob[];
Object.defineProperty(URL,'createObjectURL',{configurable:true,writable:true,value:()=>''});
Object.defineProperty(URL,'revokeObjectURL',{configurable:true,writable:true,value:()=>{}});
beforeEach(()=>{
 localStorage.clear();downloaded=[];
 vi.stubGlobal('fetch',vi.fn(()=>{throw new Error('Backup must never use network');}));
 vi.spyOn(URL,'createObjectURL').mockImplementation(blob=>{downloaded.push(blob as Blob);return 'blob:synthetic-backup';});
 vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>{});
 vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
});
afterEach(()=>{cleanup();expect(fetch).not.toHaveBeenCalled();vi.restoreAllMocks();vi.unstubAllGlobals();});
function open(){return render(<MemoryRouter><StashPage/></MemoryRouter>);}
function choose(text=documentOf(),name='synthetic.json'){
 fireEvent.change(screen.getByLabelText('选择学习记录 JSON'),{target:{files:[new File([text],name,{type:'application/json'})]}});
}
function read(blob:Blob):Promise<string>{return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsText(blob);});}
it('exports only the two learning keys through a real download button, without exporting unrelated secrets',async()=>{
 localStorage.setItem(STASH,JSON.stringify([item('old','本机合成句')]));localStorage.setItem('unrelated.private','NEVER_EXPORT');
 open();fireEvent.click(screen.getByRole('button',{name:'下载学习记录'}));
 expect(downloaded).toHaveLength(1);const text=await read(downloaded[0]);
 expect(JSON.parse(text)).toEqual({schema:'listen-state/1',[STASH]:[item('old','本机合成句')],[LAST]:null});
 expect(text).not.toContain('NEVER_EXPORT');expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-backup');
 expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce();
});
it('file input previews without writing; explicit confirmation merges and refreshes the actual stash',async()=>{
 const original=JSON.stringify([item('old','本机合成句')]);localStorage.setItem(STASH,original);
 open();choose();await screen.findByRole('button',{name:'确认合并导入'});
 expect(localStorage.getItem(STASH)).toBe(original);expect(localStorage.getItem(LAST)).toBeNull();
 expect(screen.getByText(/不是已播放/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'确认合并导入'}));
 await screen.findByText('合成学习原句');expect(JSON.parse(localStorage.getItem(STASH)!)).toHaveLength(2);
 expect(JSON.parse(localStorage.getItem(LAST)!).t).toBe(0);expect(screen.queryByRole('button',{name:'确认合并导入'})).toBeNull();
});
it('cancel and malformed/new-version selections cannot write or retain an old confirm action',async()=>{
 open();choose();await screen.findByRole('button',{name:'确认合并导入'});fireEvent.click(screen.getByRole('button',{name:'取消预览'}));
 expect(localStorage.length).toBe(0);choose('{');await screen.findByRole('alert');
 expect(screen.queryByRole('button',{name:'确认合并导入'})).toBeNull();
 choose(documentOf().replace('listen-state/1','listen-state/999'));await waitFor(()=>expect(screen.getByRole('alert').textContent).toMatch(/版本/));
 expect(localStorage.length).toBe(0);
});
it('detects local edits after preview, refuses stale confirmation and preserves both records',async()=>{
 open();choose();await screen.findByRole('button',{name:'确认合并导入'});
 const newer=JSON.stringify([item('other','另一页面新收下的句子')]);localStorage.setItem(STASH,newer);
 fireEvent.click(screen.getByRole('button',{name:'确认合并导入'}));
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toMatch(/变化|重新预览/));
 expect(localStorage.getItem(STASH)).toBe(newer);expect(localStorage.getItem(LAST)).toBeNull();
});
it('corrupt local storage does not crash StashPage or export an empty backup over the corruption',async()=>{
 localStorage.setItem(STASH,'{"not":"an array"}');open();
 fireEvent.click(screen.getByRole('button',{name:'下载学习记录'}));
 expect(screen.getByRole('alert').textContent).toMatch(/本机.*损坏/);expect(downloaded).toHaveLength(0);
 expect(localStorage.getItem(STASH)).toBe('{"not":"an array"}');
});
it('a failed second data write restores exact original bytes and reports failure, not success',async()=>{
 const original='[\n'+JSON.stringify(item('old','本机合成句'))+'\n]';localStorage.setItem(STASH,original);open();choose();await screen.findByRole('button',{name:'确认合并导入'});
 const real=Storage.prototype.setItem;vi.spyOn(Storage.prototype,'setItem').mockImplementation(function(this:Storage,k,v){if(k===LAST)throw new DOMException('synthetic quota','QuotaExceededError');real.call(this,k,v);});
 fireEvent.click(screen.getByRole('button',{name:'确认合并导入'}));
 expect(screen.getByRole('alert').textContent).toMatch(/失败.*已恢复/);expect(localStorage.getItem(STASH)).toBe(original);expect(localStorage.getItem(LAST)).toBeNull();
});
it('oversized files are rejected before FileReader and cannot create a preview',async()=>{
 open();const file=new File(['{}'],'oversized.json');Object.defineProperty(file,'size',{value:2*1024*1024+1});
 const spy=vi.spyOn(FileReader.prototype,'readAsText');fireEvent.change(screen.getByLabelText('选择学习记录 JSON'),{target:{files:[file]}});
 expect(screen.getByRole('alert').textContent).toMatch(/2 MiB/);expect(spy).not.toHaveBeenCalled();expect(localStorage.length).toBe(0);
});
it('previews actual new quotes and request identity before confirmation, rendering markup as literal text',async()=>{
 open();choose(documentOf([item('markup','<img src=x onerror=alert(1)>合成句')]));
 await screen.findByRole('button',{name:'确认合并导入'});
 expect(screen.getByText(/<img src=x onerror=alert\(1\)>合成句/)).toBeTruthy();expect(document.querySelector('img')).toBeNull();
 expect(screen.getByText(/jgy-001.*0.*秒/)).toBeTruthy();expect(localStorage.length).toBe(0);
});
it('a blocked repeat download clears the old success notice and preserves local records',()=>{
 open();fireEvent.click(screen.getByRole('button',{name:'下载学习记录'}));expect(screen.getByRole('status')).toBeTruthy();
 vi.mocked(URL.createObjectURL).mockImplementationOnce(()=>{throw new Error('合成下载被阻止');});
 fireEvent.click(screen.getByRole('button',{name:'下载学习记录'}));expect(screen.getByRole('alert')).toBeTruthy();expect(screen.queryByRole('status')).toBeNull();expect(localStorage.length).toBe(0);
});
it('durable recovery survives a real component remount, downloads original state and explicitly restores it',async()=>{
 const original=JSON.stringify([item('old','原始合成句')]);localStorage.setItem(STASH,original);const view=open();choose();await screen.findByRole('button',{name:'确认合并导入'});
 const real=Storage.prototype.setItem;let deny=true;vi.spyOn(Storage.prototype,'setItem').mockImplementation(function(this:Storage,k,v){if(deny&&(k===LAST||k===STASH&&v===original))throw new Error('synthetic quota');real.call(this,k,v);});
 fireEvent.click(screen.getByRole('button',{name:'确认合并导入'}));expect(screen.getByRole('alert').textContent).toMatch(/恢复.*未完成/);
 view.unmount();open();expect(screen.queryByRole('button',{name:'确认合并导入'})).toBeNull();
 expect((screen.getByLabelText('选择学习记录 JSON') as HTMLInputElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'下载导入前原记录'}));expect(JSON.parse(await read(downloaded[0]))[STASH]).toEqual([item('old','原始合成句')]);
 deny=false;fireEvent.click(screen.getByRole('button',{name:'重试恢复原记录'}));
 expect(localStorage.getItem(STASH)).toBe(original);expect(localStorage.getItem(LAST)).toBeNull();
 expect(screen.queryByText('合成学习原句')).toBeNull();expect(screen.queryByRole('button',{name:'重试恢复原记录'})).toBeNull();
});
it('FileReader error reports a plain failure and exposes no confirmation',()=>{
 open();vi.spyOn(FileReader.prototype,'readAsText').mockImplementation(function(this:FileReader){this.dispatchEvent(new ProgressEvent('error'));});
 choose();expect(screen.getByRole('alert').textContent).toMatch(/没能读取/);expect(screen.queryByRole('button',{name:'确认合并导入'})).toBeNull();expect(localStorage.length).toBe(0);
});
it('superseded file loads cannot restore an old preview or write stale data',async()=>{
 open();const readers:FileReader[]=[];vi.spyOn(FileReader.prototype,'readAsText').mockImplementation(function(this:FileReader){readers.push(this);});
 choose(documentOf([item('a','first')]));choose(documentOf([item('b','second')]));
 Object.defineProperty(readers[0],'result',{value:documentOf([item('a','first')])});act(()=>readers[0].dispatchEvent(new ProgressEvent('load')));
 expect(screen.queryByRole('button',{name:'确认合并导入'})).toBeNull();
 Object.defineProperty(readers[1],'result',{value:documentOf([item('b','second')])});act(()=>readers[1].dispatchEvent(new ProgressEvent('load')));
 await screen.findByRole('button',{name:'确认合并导入'});expect(localStorage.length).toBe(0);
 fireEvent.click(screen.getByRole('button',{name:'确认合并导入'}));expect(JSON.parse(localStorage.getItem(STASH)!)[0].id).toBe('b');
});
it('leaving with a pending file aborts it; late load is ignored without a storage write',()=>{
 const view=open();let pending:FileReader;vi.spyOn(FileReader.prototype,'readAsText').mockImplementation(function(this:FileReader){pending=this;});
 const abort=vi.spyOn(FileReader.prototype,'abort');choose();view.unmount();expect(abort).toHaveBeenCalled();
 Object.defineProperty(pending!,'result',{value:documentOf()});act(()=>pending!.dispatchEvent(new ProgressEvent('load')));expect(localStorage.length).toBe(0);
});
it('denied storage reads are visible without crashing or pretending a backup was downloaded',()=>{
 vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new DOMException('synthetic denied','SecurityError');});
 open();expect(screen.getByRole('alert').textContent).toMatch(/读取/);
 fireEvent.click(screen.getByRole('button',{name:'下载学习记录'}));expect(downloaded).toHaveLength(0);expect(screen.getByRole('alert').textContent).toMatch(/读取/);
});
it('explicit keep-current recovery clears only the journal and leaves the visible records unchanged',async()=>{
 const original=JSON.stringify([item('old','原始合成句')]);localStorage.setItem(STASH,original);open();choose();await screen.findByRole('button',{name:'确认合并导入'});
 const real=Storage.prototype.setItem;let deny=true;vi.spyOn(Storage.prototype,'setItem').mockImplementation(function(this:Storage,k,v){if(deny&&(k===LAST||k===STASH&&v===original))throw new Error('synthetic quota');real.call(this,k,v);});
 fireEvent.click(screen.getByRole('button',{name:'确认合并导入'}));const current=localStorage.getItem(STASH);deny=false;
 fireEvent.click(screen.getByRole('button',{name:'保留当前记录并清理恢复备份'}));expect(localStorage.getItem(STASH)).toBe(current);expect(localStorage.getItem(LAST)).toBeNull();
 expect(screen.queryByRole('button',{name:'下载导入前原记录'})).toBeNull();expect(screen.getByText('合成学习原句')).toBeTruthy();
});
