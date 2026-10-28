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

export function CiteLinks({ cite }: { cite: Citation }) {
  const when = cite.start_s != null ? formatT(cite.start_s) : "";
  return (
    <p className="cite-links">
      {cite.youtube_t_url && (
        <a href={cite.youtube_t_url} target="_blank" rel="noreferrer">
          打开 YouTube{when ? ` · ${when}` : ""}
        </a>
      )}
      {cite.t_url && <code>{cite.t_url}</code>}
    </p>
  );
}
