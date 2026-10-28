import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { ApiError, fetchPaths } from "../api/client";
import { categoryCaption } from "../graph/styleRegistry";
import { CiteLinks } from "../panel/format";
import { ErrorState } from "../panel/ErrorState";
import { HeldList } from "../panel/HeldList";
import type { PathsResponse } from "../types";
import type { ShellContext } from "../App";

export function PathsPage() {
  const { focus } = useOutletContext<ShellContext>();
  const [data, setData] = useState<PathsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    setError(null);
    setData(null);
    fetchPaths(focus)
      .then((body) => {
        if (!ac.signal.aborted) setData(body);
      })
      .catch((err: unknown) => {
        if (ac.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "接口没有返回路径");
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, [focus]);

  return (
    <div className="paths">
      {loading && <p className="status">正在读取路径…</p>}
      {error && <ErrorState title="路径接口不可用" detail={error} />}
      {data && (
        <>
          <p className="disclaimer">{data.disclaimer}</p>
          {data.tracks.length === 0 && (
            <p className="empty">
              这个焦点下没有通过硬闸的 candidate 边，所以这里不列出证型，也不做排行。
            </p>
          )}
          <div className="tracks">
            {data.tracks.map((track) => (
              <section key={track.syndrome_id} className="track">
                <h2>{track.label}</h2>
                <p className="muted">同权并列，不分先后</p>
                {track.treats.length > 0 && (
                  <ul className="cards">
                    {track.treats.map((card) => (
                      <li key={`t-${card.kp_id}-${card.subj_id}`} className="card">
                        <p className="badge">{categoryCaption(card.category)} · treats · candidate</p>
                        <h3>{card.label}</h3>
                        {card.statement && <p>{card.statement}</p>}
                        {card.evidence_quote && <blockquote>{card.evidence_quote}</blockquote>}
                        <CiteLinks cite={card} />
                      </li>
                    ))}
                  </ul>
                )}
                {track.cards.length === 0 && <p className="muted">这条证下没有通过硬闸的 indicates。</p>}
                <ul className="cards">
                  {track.cards.map((card) => (
                    <li key={`${card.kp_id}-${card.subj_id}`} className="card">
                      <p className="badge">{categoryCaption(card.category)} · indicates · candidate</p>
                      <h3>{card.label}</h3>
                      {card.statement && <p>{card.statement}</p>}
                      {card.evidence_quote && <blockquote>{card.evidence_quote}</blockquote>}
                      <p className="muted">{card.kp_id}</p>
                      <CiteLinks cite={card} />
                    </li>
                  ))}
                </ul>
                <p>
                  <Link to={`/graph?focus=${encodeURIComponent(track.syndrome_id)}`}>在关系图里打开</Link>
                </p>
              </section>
            ))}
          </div>
          <HeldList held={data.held} />
        </>
      )}
    </div>
  );
}
