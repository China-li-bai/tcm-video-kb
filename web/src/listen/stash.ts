import type { LastWatch, StashItem } from "./types";

export const STASH_KEY = "renji.listen.stash.v1";
export const LAST_KEY = "renji.listen.lastWatch.v1";

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

export function listStash(): StashItem[] {
  const value = readJson<unknown>(STASH_KEY, []);
  // Display safely without rewriting damaged storage; strict backup reports it.
  return Array.isArray(value) ? value.filter((item): item is StashItem =>
    item && typeof item === "object" && ["id", "videoId", "title", "text", "savedAt"].every(k => typeof item[k] === "string")) : [];
}

export function saveStashItem(item: Omit<StashItem, "id" | "savedAt"> & { id?: string }): StashItem {
  const items = listStash();
  const next: StashItem = {
    id: item.id ?? `stash-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    videoId: item.videoId,
    title: item.title,
    text: item.text,
    t: item.t,
    savedAt: new Date().toISOString(),
  };
  // de-dupe by text+video
  const filtered = items.filter((x) => !(x.videoId === next.videoId && x.text === next.text));
  filtered.unshift(next);
  writeJson(STASH_KEY, filtered.slice(0, 200));
  return next;
}

export function getStashItem(id: string): StashItem | undefined {
  return listStash().find((x) => x.id === id);
}

export function removeStashItem(id: string) {
  writeJson(
    STASH_KEY,
    listStash().filter((x) => x.id !== id),
  );
}

export function getLastWatch(): LastWatch | null {
  const value = readJson<LastWatch | null>(LAST_KEY, null);
  return value && typeof value === "object" && typeof value.videoId === "string" && typeof value.title === "string" ? value : null;
}

export function setLastWatch(watch: LastWatch) {
  writeJson(LAST_KEY, watch);
}
