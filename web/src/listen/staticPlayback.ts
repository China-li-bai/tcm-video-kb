/** All positions are requested whole seconds, never observed media time. */
export function requestedSeconds(value: unknown): number {
  const seconds = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? Math.floor(seconds) : 0;
}

/** The nearest preceding row (or the first row before its start) is selected.
 * Highlight is a navigation affordance, not evidence of playback or completion.
 */
export function selectedPositionIndex(rows: {t: number; end?: number; key?: string}[], requestedS: number, selectedKey?: string): number {
  // A click selects its exact row even when its fractional start is rounded for the iframe.
  const explicit = selectedKey == null ? -1 : rows.findIndex(row => row.key === selectedKey);
  if (explicit >= 0) return explicit;
  let selected = 0;
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    if (row.end != null && requestedS >= row.t && requestedS < row.end) return i;
    if (row.t <= requestedS) selected = i;
    else break;
  }
  return selected;
}

export type FramePhase = 'pending' | 'responded' | 'failed';
export function nextFramePhase(phase: FramePhase, event: {type: 'load' | 'error'}): FramePhase {
  // A new keyed request, not a later load event, clears a reported error.
  if (phase === 'failed') return phase;
  return event.type === 'error' ? 'failed' : 'responded';
}
export function frameNotice(phase: FramePhase): string {
  if (phase === 'failed') return '未能打开播放器页面。可重试或用原平台听。';
  if (phase === 'responded') return '播放器页面有响应；本站不能确认播放或跳秒是否成功。';
  return '已请求打开播放器，尚未收到页面响应。若无画面，可重试或用原平台听。';
}
