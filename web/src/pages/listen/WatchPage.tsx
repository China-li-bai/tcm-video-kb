import { DeskStage } from "../../layout/DeskStage";
import { WatchFrame } from "../../layout/WatchFrame";
import { StaticYouTubePlayer } from "../../listen/StaticYouTubePlayer";
import { requestedSeconds, selectedPositionIndex } from "../../listen/staticPlayback";
import { hasPublicTranscript } from "../../listen/transcriptCoverage";
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
  loadKnowledgePoints,
  pickClaimsNear,
  type KnowledgePoint,
} from "../../listen/knowledgePoints";
import {
  entityTypeBadge,
  loadEntities,
  pickChipsNear,
  type EntityMention,
} from "../../listen/entities";
import { EntitySheet } from "../../listen/EntitySheet";
import {
  formatClock,
  getLecture,
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
  const requestedS = requestedSeconds(params.get("t"));

  const [tab, setTab] = useState<Tab>("script");
  const [rowSelection, setRowSelection] = useState<{videoId: string; requestedS: number; key: string; chapterId?: string} | null>(null);
  const selectedChapter = useMemo(() => {
    if (!chapters.length) return null;
    // A direct row click keeps its chapter, even across a fractional boundary.
    if (rowSelection?.videoId === videoId && rowSelection.requestedS === requestedS) {
      const explicit = chapters.find(c => c.chapter_id === rowSelection.chapterId);
      if (explicit) return explicit;
    }
    // Chapter targets use the same whole-second contract as URL/iframe start.
    return chapters.find(c => requestedS >= requestedSeconds(c.start_s) && requestedS < requestedSeconds(c.end_s))
      ?? chapters.filter(c => requestedSeconds(c.start_s) <= requestedS).at(-1) ?? chapters[0];
  }, [chapters, requestedS, videoId, rowSelection]);
  const [toast, setToast] = useState("");
  const [checkOpen, setCheckOpen] = useState(false);
  /** Progressive disclosure: ⋯ on selected line opens 问这句/收下 (first tap still seek-only). */
  const [moreOpen, setMoreOpen] = useState(false);
  const [embedRequest, setEmbedRequest] = useState<{videoId: string; revision: number} | null>(null);
  const embedRequested = embedRequest?.videoId === videoId;
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState(true);
  const [kpPoints, setKpPoints] = useState<KnowledgePoint[] | null>(null);
  const [kpLoading, setKpLoading] = useState(true);
  const [entityMentions, setEntityMentions] = useState<EntityMention[] | null>(null);
  const [entitiesLoading, setEntitiesLoading] = useState(true);
  const [chipEntity, setChipEntity] = useState<EntityMention | null>(null);
  /** Whether the selected navigation row is outside the transcript viewport. */
  const [awayFromSelected, setAwayFromSelected] = useState(false);
  const selectedRowRef = useRef<HTMLDivElement | null>(null);
  const scriptScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setEmbedRequest(null);
  }, [videoId]);

  useEffect(() => {
    setRowSelection(previous => previous?.videoId === videoId && previous.requestedS === requestedS ? previous : null);
  }, [videoId, requestedS]);

  useEffect(() => {
    let cancelled = false;
    setSegments(null);
    if (!hasPublicTranscript(videoId)) {
      setTranscriptLoading(false);
      return;
    }
    setTranscriptLoading(true);
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
    let cancelled = false;
    setKpLoading(true);
    setKpPoints(null);
    loadKnowledgePoints(videoId).then((file) => {
      if (cancelled) return;
      setKpPoints(file?.points ?? null);
      setKpLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  useEffect(() => {
    let cancelled = false;
    setEntityMentions(null);
    setEntitiesLoading(true);
    setChipEntity(null);
    loadEntities(videoId).then((file) => {
      if (cancelled) return;
      setEntityMentions(file?.mentions ?? null);
      setEntitiesLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  const hasRealScript = Boolean(segments && segments.length > 0);

  const utterances: DisplayUtter[] = useMemo(() => {
    if (hasRealScript && segments) {
      let list = segments;
      // 有章节时只展示当前章时间窗，避免整集数千句一次挂上 DOM。
      if (selectedChapter) {
        const lo = selectedChapter.start_s;
        const hi = selectedChapter.end_s;
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
    if (!transcriptLoading && selectedChapter) {
      return chapterAsUtterances(selectedChapter).map((u, i) => ({
        key: `c-${selectedChapter.chapter_id}-${i}`,
        t: u.t,
        text: u.text,
      }));
    }
    return [];
  }, [hasRealScript, segments, selectedChapter, transcriptLoading]);

  const selectedKey = rowSelection?.videoId === videoId && rowSelection.requestedS === requestedS
    ? rowSelection.key : undefined;
  const selectedUtterIdx = selectedPositionIndex(utterances, requestedS, selectedKey);

  useEffect(() => {
    const el = selectedRowRef.current;
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedUtterIdx, tab, hasRealScript, videoId, selectedChapter?.chapter_id]);

  useEffect(() => {
    setMoreOpen(false);
  }, [selectedUtterIdx, videoId]);

  useEffect(() => {
    if (tab !== "script") {
      setAwayFromSelected(false);
      return;
    }
    const el = selectedRowRef.current;
    const root = scriptScrollRef.current;
    if (!el || !root) {
      setAwayFromSelected(false);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        setAwayFromSelected(!entry.isIntersecting);
      },
      {
        // Root = transcript pane (not the window), so FAB tracks pane scroll.
        root,
        threshold: 0.35,
        rootMargin: "-12% 0px -18% 0px",
      },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [selectedUtterIdx, tab, utterances.length, hasRealScript, transcriptLoading, videoId, selectedChapter?.chapter_id]);

  useEffect(() => {
    if (!lecture) return;
    setLastWatch({
      videoId: lecture.id,
      title: lecture.title,
      chapterId: selectedChapter?.chapter_id,
      chapterTitle: selectedChapter?.title,
      t: requestedS,
      updatedAt: new Date().toISOString(),
    });
  }, [lecture, selectedChapter, requestedS]);

  const selectedUtter = utterances[selectedUtterIdx] ?? utterances[0];
  const quote = selectedUtter?.text || selectedChapter?.summary || lecture?.title || "";
  const where = lecture
    ? `${lecture.seriesLabel} · ${lecture.id}${selectedUtter ? ` · 约 ${formatClock(selectedUtter.t)}` : ""}`
    : "";
  const askT = selectedUtter?.t ?? requestedS;
  const nearbyClaims = useMemo(
    () => pickClaimsNear(kpPoints ?? [], askT),
    [kpPoints, askT],
  );
  const activeChips = useMemo(() => {
    if (!selectedUtter) return [];
    return pickChipsNear(
      entityMentions ?? [],
      selectedUtter.t,
      selectedUtter.end,
    );
  }, [entityMentions, selectedUtter]);

  function flash(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(""), 1800);
  }

  function writeTimeToUrl(t: number) {
    const floorT = requestedSeconds(t);
    const next = new URLSearchParams(params);
    if (floorT > 0) next.set("t", String(floorT));
    else next.delete("t");
    setSearchParams(next, { replace: true });
  }

  function requestEmbed() {
    setEmbedRequest(previous => ({videoId, revision: (previous?.revision ?? 0) + 1}));
  }

  function seekTo(t: number, selectedRowKey?: string) {
    const seconds = requestedSeconds(t);
    setRowSelection(selectedRowKey ? {videoId, requestedS: seconds, key: selectedRowKey, chapterId: selectedChapter?.chapter_id} : null);
    writeTimeToUrl(seconds);
    requestEmbed();
  }

  function onPickUtter(i: number) {
    const row = utterances[i];
    if (!row) return;
    if (i !== selectedUtterIdx) setMoreOpen(false);
    seekTo(row.t, row.key);
  }

  function returnToSelected() {
    const el = selectedRowRef.current;
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    setAwayFromSelected(false);
  }

  function onStash(opts?: { text?: string; t?: number }) {
    if (!lecture) return;
    saveStashItem({
      videoId: lecture.id,
      title: selectedChapter?.title || lecture.title,
      text: opts?.text || quote,
      t: opts?.t ?? selectedUtter?.t ?? selectedChapter?.start_s,
    });
    flash("已收下，放进收获匣了");
  }

  function jumpChapter(ch: Chapter) {
    setTab("script");
    seekTo(ch.start_s);
  }

  if (!lecture) {
    return (
      <DeskStage variant="watch">
        <div className="empty-card">
          <h2>找不到这一集</h2>
          <p>可能 id 写错了。回系列里挑一集听听。</p>
          <Link to="/series" className="listen-btn listen-btn-primary">
            看系列
          </Link>
        </div>
      </DeskStage>
    );
  }

  const hasChapters = hasBundledChapters(videoId);
  const showScriptEmpty = !transcriptLoading && !hasRealScript && !hasChapters;

  return (
    <WatchFrame
      fixed={
        <>
          <div className="watch-nav-row">
            <Link to="/" className="listen-text-link">
              回首页
            </Link>
            <Link to={`/series/${lecture.series}`} className="series-chip">
              {lecture.seriesLabel} · {lecture.id}
            </Link>
          </div>

          <section className="player-card">
            <h1 className="player-title">{selectedChapter?.title || lecture.title}</h1>
            {selectedChapter && (
              <p className="player-sub">
                将遇：约 {chapterApproxMin(selectedChapter)} 分钟 · {formatClock(selectedChapter.start_s)}–
                {formatClock(selectedChapter.end_s)}
              </p>
            )}

            <StaticYouTubePlayer
              key={`${videoId}:${requestedS}:${embedRequested ? embedRequest?.revision : "closed"}`}
              youtubeId={lecture.youtubeId}
              title={lecture.title}
              requestedS={requestedS}
              requested={embedRequested}
              onRequest={requestEmbed}
            />
            <div className="player-position">
              <span>请求定位 {formatClock(requestedS)}</span>
              <span>目录时长 {lecture.duration || "未标注"}</span>
            </div>
            <p className="player-fallback">文稿高亮只表示所选位置，不会跟着播放自动翻页。</p>
          </section>
        </>
      }
      tabs={
        <>
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
        </>
      }
      scriptScrollRef={scriptScrollRef}
      overlays={
        <>
          <CheckSheet
            open={checkOpen}
            quote={quote}
            where={where}
            t={askT}
            claims={nearbyClaims}
            claimsLoading={kpLoading}
            claimsUnavailable={!kpLoading && kpPoints === null}
            onClose={() => setCheckOpen(false)}
            onListen={() => {
              setCheckOpen(false);
              if (selectedUtter) onPickUtter(selectedUtterIdx);
              else requestEmbed();
            }}
            onStash={() => {
              onStash({ text: quote, t: selectedUtter?.t });
              setCheckOpen(false);
            }}
            onListenClaim={(claim) => {
              setCheckOpen(false);
              seekTo(claim.start_s);
            }}
          />

          <EntitySheet
            open={Boolean(chipEntity)}
            mention={chipEntity}
            videoId={videoId}
            t={askT}
            onClose={() => setChipEntity(null)}
            onListen={() => {
              setChipEntity(null);
              if (selectedUtter) onPickUtter(selectedUtterIdx);
              else requestEmbed();
            }}
          />

          {toast && <div className="listen-toast">{toast}</div>}
        </>
      }
    >
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
                    selectedChapter?.chapter_id === ch.chapter_id ? "chapter-row active" : "chapter-row"
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
            {!transcriptLoading && !hasRealScript && hasPublicTranscript(videoId) && (
              <div className="empty-inline" role="status">这集的句级文稿暂时没能打开。先听原讲；稍后刷新再试。下面若有章节摘要，它不是逐句原文。</div>
            )}
            {!entitiesLoading && entityMentions === null && hasPublicTranscript(videoId) && (
              <div className="empty-inline" role="status">这集的词条提示暂时没能打开，不影响听原讲。</div>
            )}
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
              const active = i === selectedUtterIdx;
              const showMore = active && moreOpen;
              return (
                <div
                  key={u.key}
                  ref={active ? selectedRowRef : undefined}
                  className={active ? "utter-row active" : "utter-row"}
                  onClick={() => onPickUtter(i)}
                  role="button"
                  tabIndex={0}
                  aria-pressed={active}
                  onKeyDown={(e) => {
                    // Nested ask/stash/more buttons own their keyboard activation, not a new seek.
                    if (e.target !== e.currentTarget) return;
                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPickUtter(i); }
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
                    {active && activeChips.length > 0 && (
                      <div className="utter-chips" role="list" aria-label="这句里的方证">
                        {activeChips.map((m) => (
                          <button
                            key={m.entity_id}
                            type="button"
                            className="entity-chip"
                            role="listitem"
                            onClick={(e) => {
                              e.stopPropagation();
                              setChipEntity(m);
                            }}
                          >
                            <span className="entity-chip-badge">{entityTypeBadge(m.type)}</span>
                            {m.label}
                          </button>
                        ))}
                      </div>
                    )}
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
                <span className="watch-end-label">想停一会儿，可以先收下所选句</span>
                <button
                  type="button"
                  className="listen-btn listen-btn-dark"
                  onClick={() => {
                    onStash();
                    navigate("/");
                  }}
                >
                  收下所选句并回首页
                </button>
                <button
                  type="button"
                  className="listen-text-link"
                  onClick={() => {
                    if (!selectedChapter || !chapters.length) return;
                    const idx = chapters.findIndex((c) => c.chapter_id === selectedChapter.chapter_id);
                    const next = chapters[idx + 1];
                    if (next) jumpChapter(next);
                    else flash("已经是最后一章了");
                  }}
                >
                  选下一章
                </button>
              </div>
            )}
          </div>
        )}

        {tab === "script" && awayFromSelected && utterances.length > 0 && (
          <button type="button" className="return-selected" onClick={returnToSelected}>
            回到所选句
          </button>
        )}
    </WatchFrame>
  );
}
