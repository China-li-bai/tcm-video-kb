import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CheckSheet } from "../../listen/CheckSheet";
import {
  chapterAsUtterances,
  chapterApproxMin,
  getChapters,
  hasBundledChapters,
} from "../../listen/chapters";
import {
  formatClock,
  getLecture,
  youtubeEmbedUrl,
  youtubeWatchUrl,
} from "../../listen/lectures";
import { saveStashItem, setLastWatch } from "../../listen/stash";
import {
  loadTranscript,
  type Segment,
} from "../../listen/transcript";
import type { Chapter } from "../../listen/types";

type Tab = "script" | "chapters";

type DisplayUtter = {
  key: string;
  t: number;
  end?: number;
  text: string;
  seq?: number;
};

export function WatchPage() {
  const { videoId = "" } = useParams();
  const [params, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const lecture = getLecture(videoId);
  const chapters = useMemo(() => getChapters(videoId), [videoId]);
  const startT = Number(params.get("t") || 0) || 0;

  const [tab, setTab] = useState<Tab>("script");
  const [activeChapter, setActiveChapter] = useState<Chapter | null>(null);
  const [activeUtterIdx, setActiveUtterIdx] = useState(0);
  const [toast, setToast] = useState("");
  const [checkOpen, setCheckOpen] = useState(false);
  /** Progressive disclosure: ⋯ on active line opens 问这句/收下 (first tap still seek-only). */
  const [moreOpen, setMoreOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [embedNonce, setEmbedNonce] = useState(0);
  const [seekS, setSeekS] = useState(startT);
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState(true);
  /** True when the active sentence is scrolled out of view — show 「回到正在播放」. */
  const [awayFromActive, setAwayFromActive] = useState(false);
  const activeRowRef = useRef<HTMLDivElement | null>(null);
  const skipScrollRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setTranscriptLoading(true);
    setSegments(null);
    loadTranscript(videoId).then((file) => {
      if (cancelled) return;
      setSegments(file?.segments ?? null);
      setTranscriptLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  useEffect(() => {
    setSeekS(startT);
  }, [startT, videoId]);

  useEffect(() => {
    if (!chapters.length) {
      setActiveChapter(null);
      return;
    }
    let pick = chapters[0];
    const t = seekS > 0 ? seekS : startT;
    if (t > 0) {
      const hit = chapters.find((c) => t >= c.start_s && t < c.end_s);
      if (hit) pick = hit;
    }
    setActiveChapter(pick);
  }, [chapters, startT, seekS]);

  const hasRealScript = Boolean(segments && segments.length > 0);

  const utterances: DisplayUtter[] = useMemo(() => {
    if (hasRealScript && segments) {
      let list = segments;
      // 有章节时只展示当前章时间窗，避免整集数千句一次挂上 DOM。
      if (activeChapter) {
        const lo = activeChapter.start_s;
        const hi = activeChapter.end_s;
        const sliced = segments.filter((s) => s.start_s < hi && s.end_s > lo);
        if (sliced.length) list = sliced;
      }
      return list.map((s) => ({
        key: `s-${s.seq}-${s.start_s}`,
        t: s.start_s,
        end: s.end_s,
        text: s.text,
        seq: s.seq,
      }));
    }
    if (activeChapter) {
      return chapterAsUtterances(activeChapter).map((u, i) => ({
        key: `c-${activeChapter.chapter_id}-${i}`,
        t: u.t,
        text: u.text,
      }));
    }
    return [];
  }, [hasRealScript, segments, activeChapter]);

  useEffect(() => {
    if (!utterances.length) {
      setActiveUtterIdx(0);
      return;
    }
    const t = seekS > 0 ? seekS : startT || utterances[0].t;
    let best = 0;
    for (let i = 0; i < utterances.length; i += 1) {
      const u = utterances[i];
      if (u.end != null && t >= u.t && t < u.end) {
        best = i;
        break;
      }
      if (u.t <= t) best = i;
      else break;
    }
    setActiveUtterIdx(best);
  }, [utterances, seekS, startT]);

  useEffect(() => {
    if (skipScrollRef.current) {
      skipScrollRef.current = false;
      return;
    }
    const el = activeRowRef.current;
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeUtterIdx, tab, hasRealScript]);

  useEffect(() => {
    setMoreOpen(false);
  }, [activeUtterIdx, videoId]);

  useEffect(() => {
    if (tab !== "script") {
      setAwayFromActive(false);
      return;
    }
    const el = activeRowRef.current;
    if (!el) {
      setAwayFromActive(false);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        setAwayFromActive(!entry.isIntersecting);
      },
      {
        root: null,
        // Treat "near center band" as following; leave that band → show return chip.
        threshold: 0.35,
        rootMargin: "-18% 0px -28% 0px",
      },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [activeUtterIdx, tab, utterances.length, hasRealScript, transcriptLoading]);

  useEffect(() => {
    if (!lecture) return;
    const active = utterances[activeUtterIdx];
    setLastWatch({
      videoId: lecture.id,
      title: lecture.title,
      chapterId: activeChapter?.chapter_id,
      chapterTitle: activeChapter?.title,
      t: active?.t ?? activeChapter?.start_s ?? startT,
      updatedAt: new Date().toISOString(),
    });
  }, [lecture, activeChapter, startT, utterances, activeUtterIdx]);

  const activeUtter = utterances[activeUtterIdx] ?? utterances[0];
  const quote = activeUtter?.text || activeChapter?.summary || lecture?.title || "";
  const where = lecture
    ? `${lecture.seriesLabel} · ${lecture.id}${activeUtter ? ` · 约 ${formatClock(activeUtter.t)}` : ""}`
    : "";

  function flash(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(""), 1800);
  }

  function writeTimeToUrl(t: number) {
    const floorT = Math.max(0, Math.floor(t));
    const next = new URLSearchParams(params);
    if (floorT > 0) next.set("t", String(floorT));
    else next.delete("t");
    setSearchParams(next, { replace: true });
  }

  function seekTo(t: number, opts?: { play?: boolean; scroll?: boolean }) {
    const floorT = Math.max(0, t);
    setSeekS(floorT);
    writeTimeToUrl(floorT);
    if (opts?.play !== false) {
      setPlaying(true);
      setEmbedNonce((n) => n + 1);
    }
    if (opts?.scroll === false) skipScrollRef.current = true;
  }

  function onPickUtter(i: number, play = true) {
    const u = utterances[i];
    if (!u) return;
    // First touch = seek/highlight only; secondary ⋯ reveals ask/stash.
    if (i !== activeUtterIdx) setMoreOpen(false);
    setActiveUtterIdx(i);
    seekTo(u.t, { play });
  }

  function returnToPlaying() {
    const el = activeRowRef.current;
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    setAwayFromActive(false);
  }

  function onStash(opts?: { text?: string; t?: number }) {
    if (!lecture) return;
    saveStashItem({
      videoId: lecture.id,
      title: activeChapter?.title || lecture.title,
      text: opts?.text || quote,
      t: opts?.t ?? activeUtter?.t ?? activeChapter?.start_s,
    });
    flash("已收下，放进收获匣了");
  }

  function jumpChapter(ch: Chapter) {
    setActiveChapter(ch);
    setTab("script");
    seekTo(ch.start_s, { play: true });
  }

  if (!lecture) {
    return (
      <div className="listen-stage">
        <div className="empty-card">
          <h2>找不到这一集</h2>
          <p>可能 id 写错了。回系列里挑一集听听。</p>
          <Link to="/series" className="listen-btn listen-btn-primary">
            看系列
          </Link>
        </div>
      </div>
    );
  }

  const embedStart = activeUtter?.t ?? (seekS || activeChapter?.start_s || startT);
  const hasChapters = hasBundledChapters(videoId);
  const showScriptEmpty = !transcriptLoading && !hasRealScript && !hasChapters;

  return (
    <div className="listen-stage listen-stage-watch">
      <div className="watch-nav-row">
        <Link to="/" className="listen-text-link">
          回首页
        </Link>
        <Link to={`/series/${lecture.series}`} className="series-chip">
          {lecture.seriesLabel} · {lecture.id}
        </Link>
      </div>

      <section className="player-card">
        <h1 className="player-title">{activeChapter?.title || lecture.title}</h1>
        {activeChapter && (
          <p className="player-sub">
            将遇：约 {chapterApproxMin(activeChapter)} 分钟 · {formatClock(activeChapter.start_s)}–
            {formatClock(activeChapter.end_s)}
          </p>
        )}

        {lecture.youtubeId ? (
          <div className="yt-frame-wrap">
            {playing ? (
              <iframe
                key={`${lecture.youtubeId}-${Math.floor(embedStart)}-${embedNonce}`}
                title={lecture.title}
                src={youtubeEmbedUrl(lecture.youtubeId, embedStart, { autoplay: true })}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <button type="button" className="yt-poster" onClick={() => setPlaying(true)}>
                <span className="play-orb" aria-hidden>
                  ▶
                </span>
                <span>点这里听</span>
              </button>
            )}
          </div>
        ) : (
          <div className="audio-placeholder">
            <button type="button" className="play-orb big" onClick={() => setPlaying((p) => !p)} aria-label="播放">
              {playing ? "❚❚" : "▶"}
            </button>
            <p>本集暂无嵌入片源，有原平台链接时请到系列页听。</p>
          </div>
        )}

        <div className="player-progress" aria-hidden>
          <span>{formatClock(embedStart || 0)}</span>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: "28%" }} />
          </div>
          <span>{lecture.duration || "—"}</span>
        </div>
        {lecture.youtubeId && (
          <p className="player-fallback">
            <a href={youtubeWatchUrl(lecture.youtubeId, embedStart)} target="_blank" rel="noreferrer">
              播不了？用原平台听
            </a>
          </p>
        )}
      </section>

      <section className="script-section">
        <div className="script-tabs">
          <button
            type="button"
            className={tab === "script" ? "active" : ""}
            onClick={() => setTab("script")}
          >
            文稿
          </button>
          <button
            type="button"
            className={tab === "chapters" ? "active" : ""}
            onClick={() => setTab("chapters")}
          >
            章
          </button>
        </div>

        {tab === "chapters" && (
          <ul className="chapter-list">
            {chapters.length === 0 && (
              <li className="empty-inline">这集还没有打包章节，先听上面即可。</li>
            )}
            {chapters.map((ch) => (
              <li key={ch.chapter_id}>
                <button
                  type="button"
                  className={
                    activeChapter?.chapter_id === ch.chapter_id ? "chapter-row active" : "chapter-row"
                  }
                  onClick={() => jumpChapter(ch)}
                >
                  <span className="chapter-time">{formatClock(ch.start_s)}</span>
                  <span className="chapter-title">{ch.title}</span>
                  <span className="chapter-min">约 {chapterApproxMin(ch)} 分</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {tab === "script" && (
          <div className="utter-stream">
            {transcriptLoading && <div className="empty-inline">文稿加载中…</div>}

            {showScriptEmpty && (
              <div className="empty-inline">
                <p>这集还没有对齐好的文稿。</p>
                <p className="muted-sm">
                  可以先听上面；有样例集（如伤寒 shl-001～005）可看文稿与核对。播不了时用播放器旁的原平台链接。
                </p>
              </div>
            )}

            {!transcriptLoading && !hasRealScript && hasChapters && (
              <p className="muted-sm" style={{ marginBottom: 8 }}>
                本集暂用章节摘要作阅读稿；点句可跳到大致时间。
              </p>
            )}

            {utterances.map((u, i) => {
              const active = i === activeUtterIdx;
              const showMore = active && moreOpen;
              return (
                <div
                  key={u.key}
                  ref={active ? activeRowRef : undefined}
                  className={active ? "utter-row active" : "utter-row"}
                  onClick={() => onPickUtter(i, true)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") onPickUtter(i, true);
                  }}
                >
                  <span className="utter-t">{formatClock(u.t)}</span>
                  <div className="utter-body">
                    <div className="utter-line">
                      <p>{u.text}</p>
                      {active && (
                        <button
                          type="button"
                          className={moreOpen ? "utter-more open" : "utter-more"}
                          aria-label="这句还能做什么"
                          aria-expanded={moreOpen}
                          title="这句还能做什么"
                          onClick={(e) => {
                            e.stopPropagation();
                            setMoreOpen((v) => !v);
                          }}
                        >
                          ⋯
                        </button>
                      )}
                    </div>
                    {showMore && (
                      <div className="utter-actions" role="group" aria-label="这句操作">
                        <button
                          type="button"
                          className="listen-btn listen-btn-ghost utter-action-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            setCheckOpen(true);
                            setMoreOpen(false);
                          }}
                        >
                          问这句
                        </button>
                        <button
                          type="button"
                          className="listen-btn listen-btn-ghost utter-action-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            onStash({ text: u.text, t: u.t });
                            setMoreOpen(false);
                          }}
                        >
                          收下
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {(hasRealScript || hasChapters) && (
              <div className="watch-end">
                <span className="watch-end-label">本段可以告一段落</span>
                <button
                  type="button"
                  className="listen-btn listen-btn-dark"
                  onClick={() => {
                    onStash();
                    navigate("/");
                  }}
                >
                  收下并结束今日
                </button>
                <button
                  type="button"
                  className="listen-text-link"
                  onClick={() => {
                    if (!activeChapter || !chapters.length) return;
                    const idx = chapters.findIndex((c) => c.chapter_id === activeChapter.chapter_id);
                    const next = chapters[idx + 1];
                    if (next) jumpChapter(next);
                    else flash("已经是最后一章了");
                  }}
                >
                  接着听下一段
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      <CheckSheet
        open={checkOpen}
        quote={quote}
        where={where}
        onClose={() => setCheckOpen(false)}
        onListen={() => {
          setCheckOpen(false);
          if (activeUtter) onPickUtter(activeUtterIdx, true);
          else setPlaying(true);
        }}
        onStash={() => {
          onStash({ text: quote, t: activeUtter?.t });
          setCheckOpen(false);
        }}
      />

      {tab === "script" && awayFromActive && utterances.length > 0 && (
        <button type="button" className="return-playing" onClick={returnToPlaying}>
          回到正在播放
        </button>
      )}

      {toast && <div className="listen-toast">{toast}</div>}
    </div>
  );
}
