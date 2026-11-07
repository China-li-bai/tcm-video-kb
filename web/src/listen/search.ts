import { getAllLectures, getLecture } from "./lectures";
import { getChapters } from "./chapters";
import { loadTranscript } from "./transcript";
import { TRANSCRIPT_VIDEO_IDS } from "./transcriptCoverage";
import type { Lecture } from "./types";

export type SearchHit = {
  key: string;
  kind: "quote" | "chapter" | "lecture";
  lecture: Lecture;
  /** Watch deep-link; include ?t= when known. */
  href: string;
  title: string;
  snippet: string;
  startS?: number;
};

function watchHref(id: string, startS?: number): string {
  if (startS != null && startS > 0) {
    return `/watch/${id}?t=${Math.floor(startS)}`;
  }
  return `/watch/${id}`;
}

function includesNeedle(hay: string, needle: string): boolean {
  return hay.toLowerCase().includes(needle);
}

/** Sync: lecture titles + chapter titles/summaries (already bundled). */
export function searchCatalog(q: string): SearchHit[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return [];

  const chapterHits: SearchHit[] = [];
  const lectureHits: SearchHit[] = [];
  const seenLecture = new Set<string>();

  for (const lec of getAllLectures()) {
    const chapters = getChapters(lec.id);
    for (const ch of chapters) {
      const blob = `${ch.title}\n${ch.summary}`;
      if (!includesNeedle(blob, needle)) continue;
      const startS = Number(ch.start_s) || 0;
      chapterHits.push({
        key: `ch-${ch.chapter_id}`,
        kind: "chapter",
        lecture: lec,
        href: watchHref(lec.id, startS),
        title: ch.title,
        snippet: ch.summary.slice(0, 120),
        startS,
      });
      seenLecture.add(lec.id);
    }

    const lecMatch =
      includesNeedle(lec.id, needle) ||
      includesNeedle(lec.title, needle) ||
      includesNeedle(lec.seriesLabel, needle) ||
      includesNeedle(lec.series, needle);
    if (lecMatch && !seenLecture.has(lec.id)) {
      lectureHits.push({
        key: `lec-${lec.id}`,
        kind: "lecture",
        lecture: lec,
        href: watchHref(lec.id),
        title: lec.title,
        snippet: `${lec.seriesLabel} · ${lec.id}`,
      });
      seenLecture.add(lec.id);
    }
  }

  return [...chapterHits.slice(0, 40), ...lectureHits.slice(0, 20)];
}

/** Async: sentence-level hits from bundled transcript JSON. */
export async function searchQuotes(q: string, limit = 40): Promise<SearchHit[]> {
  const needle = q.trim().toLowerCase();
  if (!needle) return [];

  const covered = new Set(TRANSCRIPT_VIDEO_IDS);
  const lectures = getAllLectures().filter((l) => covered.has(l.id));

  const hits: SearchHit[] = [];
  await Promise.all(
    lectures.map(async (lec) => {
      const file = await loadTranscript(lec.id);
      if (!file) return;
      for (const seg of file.segments) {
        if (!includesNeedle(seg.text, needle)) continue;
        const startS = Number(seg.start_s) || 0;
        hits.push({
          key: `q-${lec.id}-${seg.seq}-${startS}`,
          kind: "quote",
          lecture: lec,
          href: watchHref(lec.id, startS),
          title: lec.title,
          snippet: seg.text,
          startS,
        });
      }
    }),
  );

  hits.sort((a, b) => (a.startS ?? 0) - (b.startS ?? 0));
  // Prefer earlier lectures in catalog order, then time.
  const order = new Map(getAllLectures().map((l, i) => [l.id, i]));
  hits.sort((a, b) => {
    const oa = order.get(a.lecture.id) ?? 99;
    const ob = order.get(b.lecture.id) ?? 99;
    if (oa !== ob) return oa - ob;
    return (a.startS ?? 0) - (b.startS ?? 0);
  });
  return hits.slice(0, limit);
}

export function lectureFromId(id: string): Lecture | undefined {
  return getLecture(id);
}
