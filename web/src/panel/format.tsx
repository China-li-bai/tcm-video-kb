import { Link } from "react-router-dom";
import type { Citation } from "../types";
import { finiteSeconds, watchHref, youtubeHref } from "../listen/citationLinks";
import { hasPublicTranscript } from "../listen/transcriptCoverage";

export function formatT(seconds: number): string {
  if (!finiteSeconds(seconds)) return "未知时间";
  const sec = Math.max(0, Math.floor(seconds));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) return `${h}:${mm}:${ss}`;
  return `${m}:${ss}`;
}

/** Only identity + seconds define the site target; saved t_url is untrusted metadata. */
export function watchHrefFromCite(cite: {
  t_url?: string | null;
  video_id?: string | null;
  start_s?: number | null;
}): string | null {
  return watchHref(cite.video_id, cite.start_s);
}

export function CiteLinks({ cite }: { cite: Citation }) {
  const validTime = cite.start_s == null || finiteSeconds(cite.start_s);
  const when = finiteSeconds(cite.start_s) ? formatT(cite.start_s) : "";
  const target = watchHrefFromCite(cite);
  const source = youtubeHref(cite);
  const coverage = target
    ? hasPublicTranscript(cite.video_id!)
      ? "已有句稿，打开后以加载结果为准。"
      : "暂未公开句稿，可先听原讲。"
    : validTime ? "出处信息不完整，暂不能定位站内讲次。" : "时间信息无效，请从原平台核对出处。";
  return (
    <p className="cite-links">
      {target && (
        <Link to={target} className="cite-listen">
          听原讲{when ? ` · ${when}` : " · 未记录具体时间"}
        </Link>
      )}
      {source && (
        <a className="cite-yt" href={source} target="_blank" rel="noopener noreferrer">
          YouTube{when ? ` · ${when}` : ""}
        </a>
      )}
      <span className="muted-sm"> {coverage}</span>
    </p>
  );
}
