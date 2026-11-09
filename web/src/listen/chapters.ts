import type { Chapter } from "./types";

const modules = import.meta.glob("../data/chapters/*.json", { eager: true }) as Record<
  string,
  { default: Chapter[] } | Chapter[]
>;

const byId = new Map<string, Chapter[]>();

for (const [path, mod] of Object.entries(modules)) {
  const id = path.split("/").pop()?.replace(/\.json$/, "");
  if (!id) continue;
  const data = (mod as { default?: Chapter[] }).default ?? (mod as Chapter[]);
  byId.set(id, Array.isArray(data) ? data : []);
}

export function hasBundledChapters(videoId: string): boolean {
  return byId.has(videoId);
}

export function getChapters(videoId: string): Chapter[] {
  return byId.get(videoId) ?? [];
}

export function chapterApproxMin(ch: Chapter): number {
  const sec = Math.max(0, (ch.end_s || 0) - (ch.start_s || 0));
  return Math.max(1, Math.round(sec / 60));
}

/** 把章节摘要拆成可读「句」列表，供学一段文稿展示。 */
export function chapterAsUtterances(ch: Chapter): { t: number; text: string }[] {
  const parts = ch.summary
    .split(/[；;。！？\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length === 0) {
    return [{ t: ch.start_s, text: ch.title }];
  }
  const span = Math.max(30, (ch.end_s || ch.start_s + 60) - ch.start_s);
  const step = span / parts.length;
  return parts.map((text, i) => ({
    t: Math.floor(ch.start_s + i * step),
    text: text.endsWith("。") || text.endsWith("！") || text.endsWith("？") ? text : `${text}。`,
  }));
}

export function enrichTodayFromChapters(videoId: string): {
  chapterTitle: string;
  chapterId: string;
  approxMin: number;
  topics: string[];
  startS: number;
  summary: string;
} | null {
  const chapters = getChapters(videoId);
  if (!chapters.length) return null;
  const prefer = chapters.find((c) => /啜粥|微汗|微似/.test(c.title + c.summary))
    ?? chapters.find((c) => /桂枝汤原方|桂枝汤：/.test(c.title))
    ?? chapters[Math.min(2, chapters.length - 1)];
  const ch = prefer;
  const topics = (ch.topics || [])
    .map((t) => t.split(".").pop() || t)
    .slice(0, 3)
    .map((t) => t.replace(/_/g, ""));
  const fallbackTopics = ["营卫", "微似有汗", "啜粥"];
  return {
    chapterTitle: ch.title,
    chapterId: ch.chapter_id,
    approxMin: Math.min(20, Math.max(6, chapterApproxMin(ch))),
    topics: topics.length ? topics : fallbackTopics,
    startS: ch.start_s,
    summary: ch.summary,
  };
}
