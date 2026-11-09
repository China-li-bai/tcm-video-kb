export type Lecture = {
  id: string;
  title: string;
  series: string;
  seriesLabel: string;
  chapters: number;
  youtubeId: string | null;
  duration: string | null;
};

export type Chapter = {
  chapter_id: string;
  video_id: string;
  level: number;
  parent_id: string | null;
  seq: number;
  title: string;
  summary: string;
  start_s: number;
  end_s: number;
  topics?: string[];
  citation?: {
    youtube_id?: string;
    url?: string;
    series?: string;
    episode?: number;
    title?: string;
    start_s?: number;
    end_s?: number;
  };
};

export type StashItem = {
  id: string;
  videoId: string;
  title: string;
  text: string;
  t?: number;
  savedAt: string;
};

/** Last opened/requested position in seconds; never a measured playback head. */
export type LastWatch = {
  videoId: string;
  title: string;
  chapterId?: string;
  chapterTitle?: string;
  t?: number;
  updatedAt: string;
};
