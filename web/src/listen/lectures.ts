import catalog from "../data/lectures.json";
import type { Lecture } from "./types";

// Display correction only. Retained configs/series.yaml (book_id huangdineijing),
// configs/sources/youtube_renji.yaml and all ten original source titles agree.
// Preserve the historical catalog bytes and every source/ID field; do not use
// its erroneous label as a search alias. See docs/SERIES_DISPLAY.md.
const SERIES_DISPLAY_LABEL: Readonly<Record<string, string>> = { nj: "黄帝内经" };
const lectures: Lecture[] = ((catalog as { lectures?: Lecture[] }).lectures ?? []).map(
  (lecture) => ({ ...lecture, seriesLabel: SERIES_DISPLAY_LABEL[lecture.series] ?? lecture.seriesLabel }),
);

export function getAllLectures(): Lecture[] {
  return lectures;
}

export function getLecture(id: string): Lecture | undefined {
  return lectures.find((l) => l.id === id);
}

export type SeriesGroup = {
  id: string;
  label: string;
  count: number;
  blurb: string;
  lectures: Lecture[];
};

const SERIES_BLURB: Record<string, string> = {
  shl: "从太阳病讲起：桂枝汤、麻黄汤，把表虚表实立住。",
  jgy: "杂病门径：痰饮、虚劳、妇人诸病，跟原文走一遭。",
  zj: "经络穴位与针法：把人纪针灸一路听下来。",
  bc: "神农本草经：药性与配伍，按篇细听。",
  nj: "黄帝内经：按原讲次标题，逐集听原讲。",
};

export function getSeriesGroups(): SeriesGroup[] {
  const map = new Map<string, SeriesGroup>();
  for (const lec of lectures) {
    let g = map.get(lec.series);
    if (!g) {
      g = {
        id: lec.series,
        label: lec.seriesLabel || lec.series,
        count: 0,
        blurb: SERIES_BLURB[lec.series] || "按系列听原讲。",
        lectures: [],
      };
      map.set(lec.series, g);
    }
    g.lectures.push(lec);
    g.count += 1;
  }
  const order = ["shl", "jgy", "zj", "bc", "nj"];
  return [...map.values()].sort((a, b) => {
    const ia = order.indexOf(a.id);
    const ib = order.indexOf(b.id);
    if (ia === -1 && ib === -1) return a.id.localeCompare(b.id);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
}

export function getSeries(seriesId: string): SeriesGroup | undefined {
  return getSeriesGroups().find((g) => g.id === seriesId);
}

/** 今日一小段：优先伤寒 shl-001（太阳症上·桂枝汤相关），否则第一部有章节的讲次。 */
export function pickTodaySegment(): {
  lecture: Lecture;
  chapterTitle: string;
  chapterId?: string;
  approxMin: number;
  topics: string[];
  startS: number;
} {
  const preferred = getLecture("shl-001") ?? getLecture("shl-003") ?? lectures[0];
  return {
    lecture: preferred,
    chapterTitle: "桂枝汤：方义与服法",
    chapterId: undefined,
    approxMin: 15,
    topics: ["营卫", "微似有汗", "啜粥"],
    startS: 0,
  };
}

export function formatDurationLabel(duration: string | null | undefined): string {
  if (!duration) return "";
  // "5:33:59" or "43:46"
  const parts = duration.split(":").map(Number);
  if (parts.some((n) => Number.isNaN(n))) return duration;
  if (parts.length === 3) {
    const [h, m] = parts;
    if (h > 0) return `约 ${h} 小时 ${m} 分`;
    return `约 ${m} 分`;
  }
  if (parts.length === 2) {
    const [m] = parts;
    return `约 ${m} 分`;
  }
  return duration;
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export function searchLectures(q: string): Lecture[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return [];
  return lectures.filter((item) => {
    return (
      item.id.toLowerCase().includes(needle) ||
      item.title.toLowerCase().includes(needle) ||
      item.seriesLabel.toLowerCase().includes(needle) ||
      item.series.toLowerCase().includes(needle)
    );
  });
}

export function youtubeEmbedUrl(
  youtubeId: string,
  startS?: number,
  opts?: { autoplay?: boolean },
): string {
  const t = startS && startS > 0 ? `&start=${Math.floor(startS)}` : "";
  const ap = opts?.autoplay ? "&autoplay=1" : "";
  return `https://www.youtube.com/embed/${youtubeId}?rel=0${t}${ap}`;
}

export function youtubeWatchUrl(youtubeId: string, startS?: number): string {
  const t = startS && startS > 0 ? `&t=${Math.floor(startS)}s` : "";
  return `https://www.youtube.com/watch?v=${youtubeId}${t}`;
}
