import { DeskStage } from "../layout/DeskStage";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { fetchPaths } from "../api/client";
import { ToolFocusBar } from "../layout/ToolFocusBar";
import { useToolFocus } from "../layout/useToolFocus";
import { EvidenceExcerpt } from "../panel/EvidenceExcerpt";
import { ErrorState } from "../panel/ErrorState";
import { HeldList } from "../panel/HeldList";
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

const PATHS_FOCUS_DEFAULT = "syndrome.tai_yang_bing";

const PATHS_PRESETS = [
  { label: "太阳病", focus: "syndrome.tai_yang_bing" },
  { label: "太阳中风", focus: "syndrome.tai_yang_zhong_feng" },
  { label: "桂枝汤", focus: "formula.gui_zhi_tang" },
] as const;

type ViewMode = "cards" | "compare";

export function PathsPage() {
  const { focus, setFocus } = useToolFocus(PATHS_FOCUS_DEFAULT);
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
      .catch(() => {
        if (ac.signal.aborted) return;
        setError("暂时无法读取讲法，请稍后重试。");
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
    <DeskStage variant="tool" className="listen-tool-page listen-tool-page--scroll">
      <ToolFocusBar
        title="路径分轨"
        lead="把几种讲法放在一起，回原讲对照。"
        focus={focus}
        onFocus={setFocus}
        presets={PATHS_PRESETS}
        sibling={{
          to: `/graph?focus=${encodeURIComponent(
            focus.startsWith("formula.") ? focus : "formula.gui_zhi_tang",
          )}`,
          label: "看关系图 →",
        }}
      />
      <div className="paths-page paths-page--in-desk">
      {loading && <p className="status">正在读取路径…</p>}
      {error && <ErrorState title="路径暂时打不开" detail={error} />}
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
              点症组，相关讲法会亮起；只是帮助对照，不作诊断。
            </p>
            <div className="toolbar-row toolbar-row-end">
              <span className="learn-bound">
                各条讲法平等并列，原讲出处多的在前，不代表更适合。
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
                  含演示补充路径，请结合原讲核对
                </span>
              )}
              {vm.usedDemoSupplement && vm.usedApi && " · "}
              {vm.usedApi && <span>含已整理的讲课路径</span>}
              {!vm.usedDemoSupplement && !vm.usedApi && (
                <span>这里还没有可并列的讲法</span>
              )}
            </p>
          </div>

          <div className="paths-stage">
            <main className="paths-main" aria-label="并列讲法">
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
                  先看关系梗概，点选出处请打开{" "}
                  <Link to={`/graph?focus=${encodeURIComponent(focus)}`}>关系图</Link>
                  。
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
                <p className="field-k">怎样对照</p>
                <ul className="side-ul">
                  <li>几种讲法并列阅读，不替你选结论。</li>
                  <li>症组只帮助找线索，不能据此诊断。</li>
                  <li>有疑问时，听原讲的上下文。</li>
                </ul>
              </div>
            </aside>
          </div>

          <HeldList held={vm.held} />
        </>
      )}
      </div>
    </DeskStage>
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
            <span className="tab-origin" title="演示补充">
              ·演示
            </span>
          ) : (
            <span className="tab-origin" title="讲课整理">
              ·讲课
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
    return <span className="muted">这段讲法暂未整理症组。</span>;
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
  const trackLabel = (id: string) => tracks.find((t) => t.id === id)?.label ?? "其他讲法";

  if (!show.length) {
    return (
      <p className="paths-empty">
        这里暂未整理出对应的讲法，可以换一轨或清除症组试试。
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
                      {h.origin === "demo" ? "演示补充" : "讲课整理"}
                    </span>
                  </span>
                  <h2 className="hyp-title">{h.title}</h2>
                  <p className="hyp-target">对照：{h.target_label || "—"}</p>
                </div>
                <div className="hyp-meta">
                  <span className="evidence-stat" title="原讲出处数量，不代表诊断把握">
                    出处 {evidenceCount(h)} 条
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
                <p className="field-k">原讲句子与出处</p>
                <div className="cite-list hyp-cites">
                  {(h.citations || []).length === 0 && (
                    <p className="muted">暂未找到原讲出处。</p>
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
          当前症组暂未对应到这些讲法。可清除筛选，继续对照。
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
  return <EvidenceExcerpt cite={cite} quote={cite.evidence} />;
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
        这里暂未整理出对应的讲法，可以换一轨或清除症组试试。
      </p>
    );
  }

  const trackLabel = (id: string) => vm.tracks.find((t) => t.id === id)?.label ?? "其他讲法";

  const fields: { k: string; fn: (h: UiHypothesis) => ReactNode }[] = [
    { k: "讲法", fn: (h) => trackLabel(h.track_id) },
    { k: "来源", fn: (h) => (h.origin === "demo" ? "演示补充" : "讲课整理") },
    { k: "对照", fn: (h) => h.target_label || "—" },
    { k: "路径摘要", fn: (h) => h.path_summary },
    { k: "参考来源", fn: (h) => (h.source_layers || []).join(" · ") },
    {
      k: "出处数量",
      fn: (h) => `${evidenceCount(h)} 条（不代表诊断把握）`,
    },
    {
      k: "回听原讲",
      fn: (h) => (
        <>
          {(h.citations || []).map((c, i) => (
            <CiteCard key={i} cite={c} />
          ))}
        </>
      ),
    },
  ];

  return (
    <div className="compare-wrap">
      <p className="compare-note">
        把讲法和原句放在一起读，不分高下；有疑问就回听上下文。
      </p>
      <div className="compare-scroll">
        <table className="compare-table" aria-label="讲法对照">
          <thead>
            <tr>
              <th scope="col">对照阅读</th>
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
