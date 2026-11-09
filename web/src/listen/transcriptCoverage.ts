/**
 * Video ids that ship sentence-level public transcripts (web/public/transcripts).
 * Keep in sync with export script DEFAULT_IDS / newly exported batches (P5).
 * searchQuotes only scans these so we don't 404-hammer the whole catalog.
 */
export const TRANSCRIPT_VIDEO_IDS: readonly string[] = [
  "shl-001",
  "shl-002",
  "shl-003",
  "shl-004",
  "shl-005",
  "shl-006",
  "shl-007",
  "shl-008",
  "jgy-001",
  "jgy-002",
  "jgy-003",
  "jgy-004",
  "jgy-005",
  "jgy-006",
  "jgy-007",
  "jgy-008",
  "jgy-009",
  "jgy-010",
  "jgy-011",
  "jgy-012",
  "bc-001",
] as const;

export function hasPublicTranscript(videoId: string): boolean {
  return TRANSCRIPT_VIDEO_IDS.includes(videoId);
}
