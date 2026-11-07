import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { ApiError, fetchPaths } from "../api/client";
import { CiteLinks, formatT, watchHrefFromCite } from "../panel/format";
import { ErrorState } from "../panel/ErrorState";
import { HeldList } from "../panel/HeldList";
import type { ShellContext } from "../layout/AppShell";
import {
  buildPathsViewModel,
  evidenceCount,
  kindZh,
  type CiteItem,
  type PathsViewModel,
  type SymFilter,
  type UiHypothesis,
  type UiTrack,
} from "./paths/model";

type ViewMode = "cards" | "compare";

export function PathsPage() {
  const { focus } = useOutletContext<ShellContext>();
  const [vm, setVm] = useState<PathsViewModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTrack, setActiveTrack] = useState("all");
  const [selectedSyms, setSelectedSyms] = useState<Set<string>>(() => new Set());
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [miniOpen, setMiniOpen] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    setError(null);
    setVm(null);
    setActiveTrack("all");
    setSelectedSyms(new Set());
    fetchPaths(focus)
      .then((body) => {
        if (ac.signal.aborted) return;
        setVm(buildPathsViewModel(body));
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

  const scoped = useMemo(() => {
    if (!vm) return { show: [] as UiHypothesis[], matchedIds: new Set<string>() };
    const all = vm.hypotheses.slice();
    all.sort((a, b) => evidenceCount(b) - evidenceCount(a));
    const show =
      activeTrack === "all" ? all : all.filter((h) => h.track_id === activeTrack);
    const matchedIds = new Set(
      show
        .filter((h) => hypMatchesSyms(h, selectedSyms))
        .map((h) => h.id),
    );
    return { show, matchedIds };
  }, [vm, activeTrack, selectedSyms]);

  function toggleSym(id: string) {
    setSelectedSyms((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="paths-page">
      {loading && <p className="status">正在读取路径…</p>}
      {error && <ErrorState title="路径接口不可用" detail={error} />}
      {vm && (
        <>
          <div className="paths-toolbar" role="region" aria-label="分轨与筛选">
            <div className="toolbar-row">
              <span className="toolbar-k">路径分轨</span>
              <TrackTabs
                tracks={vm.tracks}
                active={activeTrack}
                onChange={setActiveTrack}
              />
            </div>
            <div className="toolbar-row">
              <span className="toolbar-k">症组筛选</span>
              <SymChips
                filters={vm.symptomFilters}
                selected={selectedSyms}
                onToggle={toggleSym}
              />
              {selectedSyms.size > 0 && (
                <button
                  type="button"
                  className="chip-clear"
                  onClick={() => setSelectedSyms(new Set())}
                >
                  清除筛选
                </button>
              )}
            </div>
            <p className="sym-hint">
              点症组芯片仅高亮相关路径、淡化无关卡，<strong>不是</strong>诊断提交。
            </p>
            <div className="toolbar-row toolbar-row-end">
              <span className="learn-bound">
                学习讲法 · 路径同权并列 · 排序仅标证据条数 · 非诊疗
              </span>
              <div className="view-toggle" role="group" aria-label="主区视图">
                <button
                  type="button"
                  className={`view-btn${viewMode === "cards" ? " is-on" : ""}`}
                  onClick={() => setViewMode("cards")}
                >
                  路径卡片
                </button>
                <button
                  type="button"
                  className={`view-btn${viewMode === "compare" ? " is-on" : ""}`}
                  onClick={() => setViewMode("compare")}
                >
                  对比表
                </button>
              </div>
            </div>
            <p className="data-origin muted">
              {vm.usedDemoSupplement && (
                <span>
                  含原型演示补充（桂枝汤 tracks / hypotheses / 症芯片）· cite 来自 seed 真实 t=
                </span>
              )}
              {vm.usedDemoSupplement && vm.usedApi && " · "}
              {vm.usedApi && <span>含接口 GET /graph/paths 证轨卡</span>}
              {!vm.usedDemoSupplement && !vm.usedApi && (
                <span>当前焦点下接口无证轨；无演示补充可合并</span>
              )}
              {vm.disclaimer ? ` · ${vm.disclaimer}` : null}
            </p>
          </div>

          <div className="paths-stage">
            <main className="paths-main" aria-label="同权假设路径">
              {viewMode === "cards" ? (
                <HypCardList
                  show={scoped.show}
                  matchedIds={scoped.matchedIds}
                  selectedSyms={selectedSyms}
                  tracks={vm.tracks}
                />
              ) : (
                <CompareTable
                  vm={vm}
                  activeTrack={activeTrack}
                  selectedSyms={selectedSyms}
                />
              )}
            </main>

            <aside className="paths-side">
              <details
                className="mini-graph"
                open={miniOpen}
                onToggle={(e) => setMiniOpen((e.target as HTMLDetailsElement).open)}
              >
                <summary>关系图摘要（辅）</summary>
                <p className="mini-hint">
                  简化链路示意；完整点选见{" "}
                  <Link to={`/graph?focus=${encodeURIComponent(focus)}`}>关系图</Link>
                  。不是仪表盘。
                </p>
                <MiniChains
                  hypotheses={
                    activeTrack === "all"
                      ? vm.hypotheses
                      : vm.hypotheses.filter((h) => h.track_id === activeTrack)
                  }
                  mutedIds={
                    selectedSyms.size === 0
                      ? new Set()
                      : new Set(
                          vm.hypotheses
                            .filter((h) => !hypMatchesSyms(h, selectedSyms))
                            .map((h) => h.id),
                        )
                  }
                />
              </details>
              <div className="side-note">
                <p className="field-k">口径提醒</p>
                <ul className="side-ul">
                  <li>无唯一证型结论、无匹配度排行、无完成态徽章</li>
                  <li>不出现「确诊为××」或「最佳/推荐」</li>
                  <li>边/badge 仅中文谓词；排序只标证据条数</li>
                </ul>
              </div>
            </aside>
          </div>

          <HeldList held={vm.held} />
        </>
      )}
    </div>
  );
}

function hypMatchesSyms(h: UiHypothesis, selected: Set<string>): boolean {
  if (selected.size === 0) return true;
  return h.symptom_ids.some((id) => selected.has(id));
}

function TrackTabs({
  tracks,
  active,
  onChange,
}: {
  tracks: UiTrack[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="track-tabs" role="tablist" aria-label="路径分轨">
      <button
        type="button"
        role="tab"
        aria-selected={active === "all"}
        className={`track-tab${active === "all" ? " is-on" : ""}`}
        onClick={() => onChange("all")}
      >
        全部（同权）
      </button>
      {tracks.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={active === t.id}
          className={`track-tab${active === t.id ? " is-on" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.origin === "demo" ? (
            <span className="tab-origin" title="原型演示补充">
              ·演
            </span>
          ) : (
            <span className="tab-origin" title="接口证轨">
              ·API
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function SymChips({
  filters,
  selected,
  onToggle,
}: {
  filters: SymFilter[];
  selected: Set<string>;
  onToggle: (id: string) => void;
}) {
  if (!filters.length) {
    return <span className="muted">暂无症组芯片（接口未提供 indicates 卡，且无演示补充）</span>;
  }
  return (
    <div
      className="sym-chips"
      role="group"
      aria-label="症组筛选（高亮相关路径，非诊断提交）"
    >
      {filters.map((f) => {
        const on = selected.has(f.id);
        return (
          <button
            key={f.id}
            type="button"
            className={`sym-chip${on ? " is-on" : ""}`}
            aria-pressed={on}
            onClick={() => onToggle(f.id)}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}

function HypCardList({
  show,
  matchedIds,
  selectedSyms,
  tracks,
}: {
  show: UiHypothesis[];
  matchedIds: Set<string>;
  selectedSyms: Set<string>;
  tracks: UiTrack[];
}) {
  const trackLabel = (id: string) => tracks.find((t) => t.id === id)?.label ?? id;

  if (!show.length) {
    return (
      <p className="paths-empty">
        当前分轨 / 症组下无匹配路径（筛选仅高亮，不提交诊断）。
      </p>
    );
  }

  const noneHit = selectedSyms.size > 0 && matchedIds.size === 0;

  return (
    <>
      <div className="hyp-list">
        {show.map((h) => {
          const muted = selectedSyms.size > 0 && !matchedIds.has(h.id);
          return (
            <article
              key={h.id}
              className={`hyp-card${muted ? " is-muted" : ""}`}
              data-hyp={h.id}
              data-track={h.track_id}
            >
              <header className="hyp-head">
                <div className="hyp-head-main">
                  <span className="hyp-track">
                    {trackLabel(h.track_id)}
                    <span className={`origin-tag is-${h.origin}`}>
                      {h.origin === "demo" ? "演示补充" : "接口"}
                    </span>
                  </span>
                  <h2 className="hyp-title">{h.title}</h2>
                  <p className="hyp-target">目标：{h.target_label || "—"}</p>
                </div>
                <div className="hyp-meta">
                  <span className="evidence-stat" title="仅标证据条数，非诊断概率">
                    证据 {evidenceCount(h)} 条
                  </span>
                  <div className="badge-row">
                    {(h.source_layers || []).map((L) => (
                      <span key={L} className={`layer-tag ${layerClass(L)}`}>
                        {L}
                      </span>
                    ))}
                  </div>
                </div>
              </header>
              <div className="hyp-body">
                <p className="field-k">路径摘要</p>
                <PathChain h={h} />
                <p className="field-k">证据条目（可点到秒）</p>
                <div className="cite-list hyp-cites">
                  {(h.citations || []).length === 0 && (
                    <p className="muted">无 cite</p>
                  )}
                  {(h.citations || []).map((c, i) => (
                    <CiteCard key={`${c.kp_id}-${i}`} cite={c} />
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {noneHit && (
        <p className="paths-empty">
          当前症组与已展示路径无交集（仅高亮/淡化，非诊断提交）。
        </p>
      )}
    </>
  );
}

function PathChain({ h }: { h: UiHypothesis }) {
  const steps = h.path_steps || [];
  if (!steps.length) {
    return <p className="path-chain-text">{h.path_summary}</p>;
  }
  return (
    <ol className="path-chain">
      {steps.map((s, i) => (
        <li key={`${s.label}-${i}`} className="path-step">
          {i > 0 && (
            <span className="path-arrow" aria-hidden>
              →
            </span>
          )}
          <span className="path-pill">
            <span className="path-kind">{kindZh(s.kind)}</span>
            {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

function CiteCard({ cite }: { cite: CiteItem }) {
  const when = cite.start_s != null ? formatT(cite.start_s) : "";
  const watchHref = watchHrefFromCite(cite);
  const yt = cite.youtube_t_url || cite.url || undefined;
  return (
    <div className="cite-card">
      <div className="cite-meta">
        <span>{cite.kp_id || "—"}</span>
        {when && <span>t={when}</span>}
      </div>
      {cite.evidence && <p className="cite-quote">「{cite.evidence}」</p>}
      {watchHref || yt ? (
        <p className="cite-links">
          {watchHref ? (
            <Link className="cite-listen" to={watchHref}>
              听原讲{when ? ` · ${when}` : ""}
            </Link>
          ) : null}
          {yt ? (
            <a className="cite-yt" href={yt} target="_blank" rel="noopener noreferrer">
              YouTube{when ? ` · ${when}` : ""}
            </a>
          ) : null}
        </p>
      ) : (
        <CiteLinks
          cite={{
            kp_id: cite.kp_id,
            video_id: cite.video_id,
            start_s: cite.start_s,
            youtube_t_url: cite.youtube_t_url,
            t_url: cite.t_url,
            quote: cite.evidence,
          }}
        />
      )}
    </div>
  );
}

function CompareTable({
  vm,
  activeTrack,
  selectedSyms,
}: {
  vm: PathsViewModel;
  activeTrack: string;
  selectedSyms: Set<string>;
}) {
  const byTrack = new Map<string, UiHypothesis>();
  for (const h of vm.hypotheses) {
    if (!byTrack.has(h.track_id)) byTrack.set(h.track_id, h);
  }
  let cols = vm.tracks.map((t) => byTrack.get(t.id)).filter(Boolean) as UiHypothesis[];
  if (activeTrack !== "all") {
    cols = cols.filter((h) => h.track_id === activeTrack);
  }
  if (selectedSyms.size > 0) {
    cols = cols.filter((h) => hypMatchesSyms(h, selectedSyms));
  }
  if (!cols.length) {
    const filtered = vm.hypotheses
      .filter((h) => (activeTrack === "all" ? true : h.track_id === activeTrack))
      .filter((h) => hypMatchesSyms(h, selectedSyms))
      .sort((a, b) => evidenceCount(b) - evidenceCount(a));
    cols = filtered.slice(0, 2);
  }

  if (!cols.length) {
    return (
      <p className="paths-empty">
        当前分轨 / 症组下无匹配路径（筛选仅高亮，不提交诊断）。
      </p>
    );
  }

  const trackLabel = (id: string) => vm.tracks.find((t) => t.id === id)?.label ?? id;

  const fields: { k: string; fn: (h: UiHypothesis) => ReactNode }[] = [
    { k: "轨名", fn: (h) => trackLabel(h.track_id) },
    { k: "来源", fn: (h) => (h.origin === "demo" ? "演示补充" : "接口") },
    { k: "目标", fn: (h) => h.target_label || "—" },
    { k: "路径摘要", fn: (h) => h.path_summary },
    { k: "来源层", fn: (h) => (h.source_layers || []).join(" · ") },
    {
      k: "证据条数",
      fn: (h) => `${evidenceCount(h)}（非诊断概率）`,
    },
    {
      k: "可点 cite",
      fn: (h) => (
        <>
          {(h.citations || []).map((c, i) => {
            const watchHref = watchHrefFromCite(c);
            const yt = c.youtube_t_url || c.url;
            const when = c.start_s != null ? formatT(c.start_s) : "";
            const label = `${c.kp_id || "cite"}${when ? ` @ ${when}` : ""}`;
            if (watchHref) {
              return (
                <span key={i}>
                  <Link className="cite-listen" to={watchHref}>
                    听原讲 · {label}
                  </Link>
                  {yt ? (
                    <>
                      {" · "}
                      <a className="cite-yt" href={yt} target="_blank" rel="noopener noreferrer">
                        YouTube
                      </a>
                    </>
                  ) : null}
                  <br />
                </span>
              );
            }
            if (yt) {
              return (
                <span key={i}>
                  <a className="cite-yt" href={yt} target="_blank" rel="noopener noreferrer">
                    {label}
                  </a>
                  <br />
                </span>
              );
            }
            return (
              <span key={i}>
                {label}
                <br />
              </span>
            );
          })}
        </>
      ),
    },
  ];

  return (
    <div className="compare-wrap">
      <p className="compare-note">
        对比两条（或多条）路径字段，<strong>无赢家 / 无推荐</strong>文案。
      </p>
      <div className="compare-scroll">
        <table className="compare-table">
          <thead>
            <tr>
              <th scope="col">字段</th>
              {cols.map((h) => (
                <th key={h.id} scope="col">
                  {h.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fields.map((f) => (
              <tr key={f.k}>
                <th scope="row">{f.k}</th>
                {cols.map((h) => (
                  <td key={h.id}>{f.fn(h)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MiniChains({
  hypotheses,
  mutedIds,
}: {
  hypotheses: UiHypothesis[];
  mutedIds: Set<string>;
}) {
  const list = hypotheses.slice().sort((a, b) => evidenceCount(b) - evidenceCount(a));
  if (!list.length) {
    return <p className="muted">无链路可摘要</p>;
  }
  return (
    <ul className="mini-chain-list">
      {list.map((h) => (
        <li
          key={h.id}
          className={`mini-chain${mutedIds.has(h.id) ? " is-muted" : ""}`}
        >
          <p className="mini-chain-title">{h.title}</p>
          <PathChain h={h} />
        </li>
      ))}
    </ul>
  );
}

function layerClass(layer: string): string {
  if (layer === "典籍") return "is-canon";
  if (layer === "讲义") return "is-lecture";
  if (layer === "主张") return "is-claim";
  return "";
}
