import {useEffect, useRef, useState} from 'react';
import type {ChangeEvent} from 'react';
import {LAST_KEY, STASH_KEY} from './stash';
import {createLearningBackup, parseLearningBackup, previewLearningImport, confirmLearningImport,
  readImportRecovery, originalRecoveryBackup, restoreImportRecovery, keepCurrentRecovery,
  MAX_BACKUP_BYTES, type ImportPlan, type ImportRecovery} from './learningBackup';

type Props = {onChange: () => void};
const message = (error: unknown) => error instanceof Error ? error.message : '操作没能完成；请保留原记录后重试。';
export function LearningBackupPanel({onChange}: Props) {
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [recovery, setRecovery] = useState<ImportRecovery | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reading, setReading] = useState(false);
  const reader = useRef<FileReader | null>(null);
  const urls = useRef(new Set<string>());
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  useEffect(() => {
    try {setRecovery(readImportRecovery()); createLearningBackup();} catch (e) {setError(message(e));}
    return () => {
      reader.current?.abort(); reader.current = null;
      for (const timer of timers.current) clearTimeout(timer);
      for (const url of urls.current) URL.revokeObjectURL(url);
      timers.current.clear(); urls.current.clear();
    };
  }, []);
  function refreshRecovery() {
    try {setRecovery(readImportRecovery());} catch (e) {setError(message(e));}
    onChange();
  }
  function download(text: string, filename: string) {
    const url = URL.createObjectURL(new Blob([text], {type:'application/json;charset=utf-8'}));
    urls.current.add(url);
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.append(link);
    try {link.click();}
    finally {
      link.remove();
      // Give the browser one task to consume the URL; clean up on route leave too.
      const timer = setTimeout(() => {URL.revokeObjectURL(url); urls.current.delete(url); timers.current.delete(timer);}, 0);
      timers.current.add(timer);
    }
    setNotice('已发起下载，请检查浏览器下载列表；文件含你的学习原句，请自己妥善保管。');
  }
  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    reader.current?.abort(); reader.current = null;
    setPlan(null); setError(''); setNotice(''); setReading(false);
    if (!file) return;
    if (file.size > MAX_BACKUP_BYTES) {setError('文件不能超过 2 MiB；没有改动本机记录。'); return;}
    const current = new FileReader(); reader.current = current; setReading(true);
    current.onload = () => {
      if (reader.current !== current) return;
      reader.current = null; setReading(false);
      try {setPlan(previewLearningImport(parseLearningBackup(String(current.result))));}
      catch (e) {setError(message(e));}
    };
    current.onerror = () => {
      if (reader.current !== current) return;
      reader.current = null; setReading(false); setError('文件没能读取；请重新选择，没有改动本机记录。');
    };
    try {current.readAsText(file);} catch {reader.current = null; setReading(false); setError('文件没能读取；没有改动本机记录。');}
  }
  function confirm() {
    if (!plan) return;
    setError(''); setNotice('');
    try {confirmLearningImport(plan); setNotice('已合并到本机记录；原有记录优先，没有上传。');}
    catch (e) {setError(message(e));}
    setPlan(null); refreshRecovery();
  }
  function recover(keepCurrent: boolean) {
    if (!recovery) return;
    setError(''); setNotice('');
    try {
      if (keepCurrent) keepCurrentRecovery(recovery); else restoreImportRecovery(recovery);
      setNotice(keepCurrent ? '已保留当前记录并清理导入恢复备份。' : '已恢复导入前的原记录。');
    } catch (e) {setError(message(e));}
    refreshRecovery();
  }
  return <section className="learning-backup" aria-label="学习记录备份">
    <h2>备份与导入学习记录</h2>
    <p className="muted-sm">只备份收获匣和上次打开的位置；不是已播放或完成记录。回想没有另存评分。文件只在本机读取，不上传、不做云同步。</p>
    <p className="muted-sm">最多 200 条、文件最多 2 MiB。导入按讲次加原文去重，编号冲突也保留本机；新句放后面，满额的跳过。本机已有的请求位置不覆盖，只有空缺时才补入。</p>
    <div className="hit-actions">
      <button type="button" className="listen-btn listen-btn-ghost" disabled={!!recovery} onClick={() => {
        setError(''); setNotice(''); try {download(createLearningBackup(), 'renji-listen-state-v1.json');} catch (e) {setError(message(e));}
      }}>下载学习记录</button>
      <label className="backup-file">选择学习记录 JSON
        <input type="file" accept=".json,application/json" disabled={!!recovery} onChange={selectFile}/>
      </label>
    </div>
    {reading && <p role="status">正在本机读取文件，还没有写入。</p>}
    {plan && <div className="backup-preview">
      <h3>导入预览，还没有写入</h3>
      <p>将新增 {plan.added} 条；重复或编号冲突 {plan.conflicts} 条；满额跳过 {plan.overflow} 条。</p>
      <p>{plan.keptLast ? '保留本机原来的请求位置。' : plan.state[LAST_KEY] ? '将补入文件里的请求位置。' : '没有需要补入的请求位置。'}</p>
      {plan.state[LAST_KEY] && <p>请求定位：{plan.state[LAST_KEY].videoId} · {plan.state[LAST_KEY].t ?? 0} 秒（不是播放头）</p>}
      {plan.added > 0 && <>
        <p className="muted-sm">拟新增原句（前 5 条，每条最多预览 160 字；导入保留全文）：</p>
        <ul>{plan.state[STASH_KEY].slice(-plan.added).slice(0, 5).map(item => <li key={item.id}>
          {item.videoId} · {Array.from(item.text).slice(0, 160).join('')}{Array.from(item.text).length > 160 ? '…' : ''}
        </li>)}</ul>
      </>}
      <p className="muted-sm">确认后合并，不会清空原记录。localStorage 多项写入不是原子事务；会先留本机恢复备份，但浏览器清除数据、设备故障或多标签同时改写仍有风险。请先下载，并暂停其它页面的收下/定位操作。</p>
      <div className="hit-actions">
        <button type="button" className="listen-btn listen-btn-primary" onClick={confirm}>确认合并导入</button>
        <button type="button" className="listen-text-link" onClick={() => setPlan(null)}>取消预览</button>
      </div>
    </div>}
    {recovery && <div className="backup-preview">
      <h3>上次导入尚未收尾，原记录备份还在本机</h3>
      <p>请先下载原记录。可以重试恢复；若要保留眼前记录，明确点击下方按钮才会清理恢复备份。</p>
      <div className="hit-actions">
        <button type="button" className="listen-btn listen-btn-ghost" onClick={() => {
          setError(''); setNotice(''); try {download(originalRecoveryBackup(recovery), 'renji-listen-before-import-v1.json');} catch (e) {setError(message(e));}
        }}>下载导入前原记录</button>
        <button type="button" className="listen-btn listen-btn-ghost" onClick={() => recover(false)}>重试恢复原记录</button>
        <button type="button" className="listen-text-link" onClick={() => recover(true)}>保留当前记录并清理恢复备份</button>
      </div>
    </div>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
  </section>;
}
