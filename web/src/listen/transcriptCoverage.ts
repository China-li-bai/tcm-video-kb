import manifest from "../data/publish-manifest.json";

/** Generated inventory is the only release selection used by search/export. */
export const TRANSCRIPT_VIDEO_IDS: readonly string[] = manifest.lectures
  .filter(row => row.has_public_transcript)
  .map(row => row.video_id);

export function hasPublicTranscript(videoId: string): boolean {
  return TRANSCRIPT_VIDEO_IDS.includes(videoId);
}
