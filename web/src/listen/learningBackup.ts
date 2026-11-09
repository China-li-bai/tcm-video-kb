import {getLecture} from './lectures';
import {STASH_KEY, LAST_KEY} from './stash';
import type {LastWatch, StashItem} from './types';

export const MAX_BACKUP_BYTES = 2 * 1024 * 1024;
export const RECOVERY_KEY = 'renji.listen.importRecovery.v1';
const KEYS = [STASH_KEY, LAST_KEY] as const;
type Key = typeof KEYS[number];
export type StoragePort = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
export type LearningState = {schema: 'listen-state/1'; [STASH_KEY]: StashItem[]; [LAST_KEY]: LastWatch | null};
type Raw = Record<Key, string | null>;
export type ImportPlan = {before: Raw; after: Raw; state: LearningState; added: number; conflicts: number; overflow: number; keptLast: boolean};
export type ImportRecovery = {raw: string; before: Raw; after: Raw};
const own = (value: object, key: string) => Object.prototype.hasOwnProperty.call(value, key);
const fail = (detail: string): never => {throw new Error(detail);};
const bytes = (text: string) => new TextEncoder().encode(text).byteLength;
function bounded(text: string) {
  if (bytes(text) > MAX_BACKUP_BYTES) fail('文件或合并后的记录不能超过 2 MiB；没有改动本机记录。');
}
function record(value: unknown, allowed: readonly string[], required: readonly string[]) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) return fail('文件格式不对：应为记录对象。');
  const r = value as Record<string, unknown>;
  if (Object.keys(r).some(k => !allowed.includes(k)) || required.some(k => !own(r, k))) fail('文件格式不对：有未知字段或缺少必要字段。');
  return r;
}
function string(value: unknown, max: number, empty = false): string {
  if (typeof value !== 'string' || value.length > max || (!empty && !value.trim())) return fail('文件格式不对：文字为空或过长。');
  return value;
}
function date(value: unknown) {
  const text = string(value, 64);
  const iso = /^\d{4}-\d{2}-\d{2}(?:T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,3})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d))?$/;
  const day = new Date(`${text.slice(0, 10)}T00:00:00.000Z`);
  if (!iso.test(text) || !Number.isFinite(Date.parse(text)) || !Number.isFinite(day.getTime()) || day.toISOString().slice(0, 10) !== text.slice(0, 10)) fail('文件格式不对：日期无效。');
  return text;
}
function seconds(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > Number.MAX_SAFE_INTEGER) return fail('文件格式不对：请求秒数无效。');
  return value;
}
function video(value: unknown) {
  const id = string(value, 128);
  if (!/^[A-Za-z0-9_-]+$/.test(id) || !getLecture(id)) fail('文件格式不对：不是现有目录中的讲次。');
  return id;
}
function stashItem(value: unknown): StashItem {
  const r = record(value, ['id','videoId','title','text','t','savedAt'], ['id','videoId','title','text','savedAt']);
  const id = string(r.id, 128);
  if (!/^[A-Za-z0-9_-]+$/.test(id)) fail('文件格式不对：收藏编号无效。');
  return {id, videoId: video(r.videoId), title: string(r.title, 1000, true), text: string(r.text, 10000),
    ...(own(r, 't') ? {t: seconds(r.t)} : {}), savedAt: date(r.savedAt)};
}
function lastWatch(value: unknown): LastWatch | null {
  if (value === null) return null;
  const r = record(value, ['videoId','title','chapterId','chapterTitle','t','updatedAt'], ['videoId','title','updatedAt']);
  const videoId = video(r.videoId);
  const result: LastWatch = {videoId, title: string(r.title, 1000, true), updatedAt: date(r.updatedAt)};
  if (own(r, 't')) result.t = seconds(r.t);
  if (own(r, 'chapterId')) {
    const id = string(r.chapterId, 160);
    if (!new RegExp(`^${videoId}\\.c[0-9]+$`).test(id)) fail('文件格式不对：章节与讲次不符。');
    result.chapterId = id;
  }
  if (own(r, 'chapterTitle')) result.chapterTitle = string(r.chapterTitle, 1000, true);
  return result;
}
function state(value: unknown): LearningState {
  const r = record(value, ['schema', ...KEYS], ['schema', ...KEYS]);
  if (r.schema !== 'listen-state/1') fail('暂不支持这个备份版本，请使用 listen-state/1 文件。');
  const items = r[STASH_KEY];
  if (!Array.isArray(items) || items.length > 200) return fail('文件格式不对：收获匣应为数组，最多 200 条。');
  return {schema:'listen-state/1', [STASH_KEY]:items.map(stashItem), [LAST_KEY]:lastWatch(r[LAST_KEY])};
}
export function parseLearningBackup(text: string): LearningState {
  bounded(text);
  let value: unknown;
  try {value = JSON.parse(text);} catch {return fail('文件不是可读取的 JSON；没有改动本机记录。');}
  return state(value);
}
function serialize(value: LearningState) {
  const text = JSON.stringify(value, null, 2);
  bounded(text);
  return text;
}
function readRaw(storage: Pick<StoragePort, 'getItem'>): Raw {
  try {return {[STASH_KEY]:storage.getItem(STASH_KEY), [LAST_KEY]:storage.getItem(LAST_KEY)};}
  catch {return fail('无法读取本机记录，浏览器可能禁用了存储；没有改动原数据。');}
}
function fromRaw(raw: Raw): LearningState {
  try {
    for (const k of KEYS) if (raw[k] !== null) bounded(raw[k]);
    return state({schema:'listen-state/1', [STASH_KEY]:raw[STASH_KEY] === null ? [] : JSON.parse(raw[STASH_KEY]),
      [LAST_KEY]:raw[LAST_KEY] === null ? null : JSON.parse(raw[LAST_KEY])});
  } catch {return fail('本机学习记录损坏或格式不兼容；未改动，请先保留浏览器中的原数据。');}
}
/** Never enumerate storage or include the recovery journal/unrelated application keys. */
export function createLearningBackup(storage: Pick<StoragePort, 'getItem'> = localStorage) {
  return serialize(fromRaw(readRaw(storage)));
}
export function previewLearningImport(incoming: LearningState, storage: StoragePort = localStorage): ImportPlan {
  if (readImportRecovery(storage)) fail('请先处理上次导入的恢复备份，再重新选择文件。');
  const before = readRaw(storage), current = fromRaw(before);
  const validated = state(incoming);
  const items = [...current[STASH_KEY]];
  const identity = (item: StashItem) => JSON.stringify([item.videoId, item.text]);
  const texts = new Set(items.map(identity)), ids = new Set(items.map(item => item.id));
  let added = 0, conflicts = 0, overflow = 0;
  for (const item of validated[STASH_KEY]) {
    if (texts.has(identity(item)) || ids.has(item.id)) {conflicts++; continue;}
    if (items.length >= 200) {overflow++; continue;}
    texts.add(identity(item)); ids.add(item.id); items.push(item); added++;
  }
  const merged: LearningState = {schema:'listen-state/1', [STASH_KEY]:items, [LAST_KEY]:current[LAST_KEY] ?? validated[LAST_KEY]};
  serialize(merged); // Also limit the resulting file, not only each input separately.
  const after = {...before};
  for (const k of KEYS) if (JSON.stringify(merged[k]) !== JSON.stringify(current[k])) after[k] = JSON.stringify(merged[k]);
  return {before, after, state:merged, added, conflicts, overflow, keptLast:current[LAST_KEY] !== null};
}
const equalRaw = (a: Raw, b: Raw) => KEYS.every(k => a[k] === b[k]);
function put(storage: StoragePort, k: Key, value: string | null) {
  if (value === null) storage.removeItem(k); else storage.setItem(k, value);
}
/** Best-effort rollback with a durable before/after journal, NOT a cross-key transaction. */
export function confirmLearningImport(plan: ImportPlan, storage: StoragePort = localStorage) {
  if (readImportRecovery(storage)) fail('请先处理上次导入的恢复备份。');
  if (!equalRaw(readRaw(storage), plan.before)) fail('本机记录已有变化，请重新预览；没有写入。');
  const changed = KEYS.filter(k => plan.before[k] !== plan.after[k]);
  if (!changed.length) return;
  const journal = JSON.stringify({schema:'listen-state-recovery/1', before:plan.before, after:plan.after});
  try {storage.setItem(RECOVERY_KEY, journal);}
  catch {return fail('导入失败：无法先保存恢复备份，可能空间不足或无权限；原记录未改动。');}
  const written: Key[] = [];
  try {
    for (const k of changed) {
      if (storage.getItem(k) !== plan.before[k]) fail('本机记录已有变化');
      put(storage, k, plan.after[k]); written.push(k);
    }
    storage.removeItem(RECOVERY_KEY);
  } catch {
    let restored = true;
    for (const k of written.reverse()) {
      try {
        if (storage.getItem(k) !== plan.after[k]) {restored = false; continue;}
        put(storage, k, plan.before[k]);
      } catch {restored = false;}
    }
    if (restored) {
      try {storage.removeItem(RECOVERY_KEY);} catch {return fail('导入失败：已恢复原记录，但恢复备份尚未清理；请处理下方恢复入口。');}
      return fail('导入失败：已恢复原记录，可能空间不足或无权限。');
    }
    return fail('导入失败且恢复尚未完成；原始备份仍保存在本机，请先下载原记录或重试恢复。');
  }
}
function rawRecord(value: unknown): Raw {
  const r = record(value, KEYS, KEYS);
  for (const k of KEYS) if (r[k] !== null && typeof r[k] !== 'string') fail('恢复备份格式不对');
  const result = {[STASH_KEY]:r[STASH_KEY] as string | null, [LAST_KEY]:r[LAST_KEY] as string | null};
  fromRaw(result);
  return result;
}
export function readImportRecovery(storage: StoragePort = localStorage): ImportRecovery | null {
  let raw: string | null;
  try {raw = storage.getItem(RECOVERY_KEY);} catch {return fail('无法读取本机恢复记录，浏览器可能禁用了存储。');}
  if (raw === null) return null;
  try {
    if (bytes(raw) > MAX_BACKUP_BYTES * 4 + 4096) fail('恢复备份过大');
    const r = record(JSON.parse(raw), ['schema','before','after'], ['schema','before','after']);
    if (r.schema !== 'listen-state-recovery/1') fail('恢复版本不对');
    return {raw, before:rawRecord(r.before), after:rawRecord(r.after)};
  } catch {return fail('本机恢复备份损坏或版本不兼容；未清除，请先保留浏览器中的数据。');}
}
function sameRecovery(recovery: ImportRecovery, storage: StoragePort) {
  if (storage.getItem(RECOVERY_KEY) !== recovery.raw) fail('恢复备份已有变化，请重新打开收获匣。');
}
export function originalRecoveryBackup(recovery: ImportRecovery) {return serialize(fromRaw(recovery.before));}
export function restoreImportRecovery(recovery: ImportRecovery, storage: StoragePort = localStorage) {
  try {
    sameRecovery(recovery, storage);
    const current = readRaw(storage);
    if (KEYS.some(k => current[k] !== recovery.before[k] && current[k] !== recovery.after[k])) fail('本机记录已有变化，不能覆盖；请先下载原记录另行合并。');
    for (const k of KEYS) if (current[k] !== recovery.before[k]) put(storage, k, recovery.before[k]);
    storage.removeItem(RECOVERY_KEY);
  } catch (error) {
    if (error instanceof Error && /变化/.test(error.message)) throw error;
    fail('恢复尚未完成；原始备份仍在本机，请下载原记录或稍后重试。');
  }
}
export function keepCurrentRecovery(recovery: ImportRecovery, storage: StoragePort = localStorage) {
  sameRecovery(recovery, storage);
  fromRaw(readRaw(storage));
  try {storage.removeItem(RECOVERY_KEY);} catch {fail('无法清理恢复备份；原始备份仍在本机。');}
}
