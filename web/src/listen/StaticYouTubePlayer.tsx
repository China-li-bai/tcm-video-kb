import { useReducer } from 'react';
import { youtubeEmbedUrl, youtubeWatchUrl } from './lectures';
import { frameNotice, nextFramePhase, requestedSeconds } from './staticPlayback';

type Props = {
  youtubeId: string | null;
  title: string;
  requestedS: number;
  requested: boolean;
  onRequest: () => void;
};

/** Parent keys this component by video + requested seconds + retry revision.
 * onLoad is a page event only. No YT API, media timer, ready/play/ended claim.
 */
export function StaticYouTubePlayer({youtubeId, title, requestedS, requested, onRequest}: Props) {
  const [phase, dispatch] = useReducer(nextFramePhase, 'pending');
  const t = requestedSeconds(requestedS);
  if (!youtubeId) return <div className="audio-placeholder"><p>本集暂无嵌入片源，有原平台链接时请到系列页听。</p></div>;
  return <>
    <div className="yt-frame-wrap">
      {requested ? <iframe
        title={title}
        src={youtubeEmbedUrl(youtubeId, t, {autoplay: true})}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        onLoad={() => dispatch({type: 'load'})}
        onError={() => dispatch({type: 'error'})}
      /> : <button type="button" className="yt-poster" onClick={onRequest}>
        <span className="play-orb" aria-hidden>▶</span><span>点这里听</span>
      </button>}
    </div>
    <p className="player-fallback" role="status">
      {requested ? frameNotice(phase) : '尚未打开播放器。点这里听，或点文稿请求从所选位置打开。'}
    </p>
    <p className="player-fallback">
      {requested && <><button type="button" className="listen-text-link" onClick={onRequest}>重新请求此位置</button>{' · '}</>}
      <a href={youtubeWatchUrl(youtubeId, t)} target="_blank" rel="noreferrer">播不了？用原平台听</a>
    </p>
  </>;
}
