import type { SeriesGroup } from './lectures';

// Presentation only: full titles verified against configs/series.yaml, not
// guessed from abbreviations. Keep #24's canonical nj reader (黄帝内经).
const FULL_TITLES: Readonly<Record<string, string>> = {
  shl: '伤寒论', jgy: '金匮要略', zj: '针灸大成', bc: '神农本草经',
};
export function seriesTitle(group: Pick<SeriesGroup, 'id' | 'label'>): string {
  return FULL_TITLES[group.id] ?? group.label;
}

/** Shared playlist cover for the series shelf and its episode header. */
export function SeriesCover() {
  return <div className="series-cover" aria-hidden="true">
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" focusable="false">
      <path d="M24 12c-5-4-12-5-19-3v28c7-2 14-1 19 3 5-4 12-5 19-3V9c-7-2-14-1-19 3Z" />
      <path d="M24 12v28M11 16c3-.3 5 .2 7 1M11 23c3-.3 5 .2 7 1M30 17c2-.8 4-1.3 7-1M30 24c2-.8 4-1.3 7-1" />
    </svg>
  </div>;
}
