import { Link } from "react-router-dom";
import type { Citation } from "../types";

export function formatT(seconds: number): string {
  const sec = Math.max(0, Math.floor(seconds));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) return `${h}:${mm}:${ss}`;
  return `${m}:${ss}`;
}

/** 站内听课深链：优先 t_url，否则由 video_id + start_s 拼出。 */
export function watchHrefFromCite(cite: {
  t_url?: string | null;
  video_id?: string | null;
  start_s?: number | null;
}): string | null {
  if (cite.t_url) return cite.t_url;
  if (cite.video_id) {
    const t = cite.start_s != null ? `?t=${Math.floor(cite.start_s)}` : "";
    return `/watch/${cite.video_id}${t}`;
  }
  return null;
}

export function CiteLinks({ cite }: { cite: Citation }) {
  const when = cite.start_s != null ? formatT(cite.start_s) : "";
  const watchHref = watchHrefFromCite(cite);
  return (
    <p className="cite-links">
      {watchHref && (
        <Link to={watchHref} className="cite-listen">
          听原讲{when ? ` · ${when}` : ""}
        </Link>
      )}
      {cite.youtube_t_url && (
        <a
          className="cite-yt"
          href={cite.youtube_t_url}
          target="_blank"
          rel="noreferrer"
        >
          YouTube{when ? ` · ${when}` : ""}
        </a>
      )}
    </p>
  );
}
