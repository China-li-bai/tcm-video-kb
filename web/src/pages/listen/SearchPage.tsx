import { DeskStage } from "../../layout/DeskStage";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { formatClock, formatDurationLabel } from "../../listen/lectures";
import { searchCatalog, searchQuotes, type SearchHit } from "../../listen/search";

export function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const initial = params.get("q") ?? "";
  const [draft, setDraft] = useState(initial);
  const q = initial.trim();

  const catalogHits = useMemo(() => (q ? searchCatalog(q) : []), [q]);
  const [quoteHits, setQuoteHits] = useState<SearchHit[]>([]);
  const [quotesLoading, setQuotesLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!q) {
      setQuoteHits([]);
      setQuotesLoading(false);
      return;
    }
    setQuotesLoading(true);
    searchQuotes(q).then((hits) => {
      if (cancelled) return;
      setQuoteHits(hits);
      setQuotesLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [q]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const needle = draft.trim();
    navigate(needle ? `/search?q=${encodeURIComponent(needle)}` : "/search");
  }

  const chapterHits = catalogHits.filter((h) => h.kind === "chapter");
  const lectureHits = catalogHits.filter((h) => h.kind === "lecture");
  const anyHit = quoteHits.length > 0 || catalogHits.length > 0;

  return (
    <DeskStage variant="narrow">
      <div className="page-hero">
        <h1>查出处</h1>
        <p>别处听到的一句话、一个方名，先在这里找找是哪一集，点进去从那一秒听。</p>
      </div>

      <form className="search-page-form" onSubmit={onSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="比如：桂枝汤、太阳病、微似有汗…"
          spellCheck={false}
          autoFocus
        />
        <button type="submit" className="listen-btn listen-btn-primary">
          搜索
        </button>
      </form>

      {!q && (
        <p className="muted-sm center">输入关键词后回车。会搜讲次、章节和已挂的原文句子，不编造出处。</p>
      )}

      {q && quotesLoading && (
        <p className="muted-sm center">正在翻原文句子…</p>
      )}

      {q && quoteHits.length > 0 && (
        <section className="listen-block">
          <h3 className="listen-block-title">原文句子 · {quoteHits.length}</h3>
          <ul className="search-hits">
            {quoteHits.map((hit) => (
              <HitCard key={hit.key} hit={hit} />
            ))}
          </ul>
        </section>
      )}

      {q && chapterHits.length > 0 && (
        <section className="listen-block">
          <h3 className="listen-block-title">章节 · {chapterHits.length}</h3>
          <ul className="search-hits">
            {chapterHits.map((hit) => (
              <HitCard key={hit.key} hit={hit} />
            ))}
          </ul>
        </section>
      )}

      {q && lectureHits.length > 0 && (
        <section className="listen-block">
          <h3 className="listen-block-title">讲次 · {lectureHits.length}</h3>
          <ul className="search-hits">
            {lectureHits.map((hit) => (
              <HitCard key={hit.key} hit={hit} />
            ))}
          </ul>
        </section>
      )}

      {q && !quotesLoading && !anyHit && (
        <section className="miss-card">
          <h2>暂时找不到可靠出处</h2>
          <p>
            库里的讲次、章节和已挂原文里没有明显对上「{q}」。换个说法再搜试试——比如方名、病名、或系列名（伤寒、金匮）。
          </p>
          <p className="muted-sm">不会编造出处。确定不了就先回听课台，从今日一小段听起。</p>
          <div className="hit-actions">
            <button
              type="button"
              className="listen-btn listen-btn-ghost"
              onClick={() => {
                setDraft("");
                navigate("/search");
              }}
            >
              换说法
            </button>
            <Link to="/" className="listen-btn listen-btn-primary">
              回首页
            </Link>
          </div>
        </section>
      )}
    </DeskStage>
  );
}

function HitCard({ hit }: { hit: SearchHit }) {
  const time =
    hit.startS != null && hit.startS > 0 ? formatClock(hit.startS) : null;
  const duration = hit.lecture.duration
    ? formatDurationLabel(hit.lecture.duration)
    : "";

  return (
    <li>
      <article className="hit-card">
        <p className="hit-label">
          {hit.kind === "quote" ? "这一句" : hit.kind === "chapter" ? "这一段" : "这一集"}
          {time ? ` · ${time}` : ""}
        </p>
        <h3>{hit.title}</h3>
        <p className="muted-sm">
          {hit.lecture.seriesLabel}
          {duration ? ` · ${duration}` : ""}
        </p>
        {hit.snippet ? <p className="hit-snippet">{hit.snippet}</p> : null}
        <div className="hit-actions">
          <Link to={hit.href} className="listen-btn listen-btn-primary">
            {time ? `从 ${time} 听` : "听原讲"}
          </Link>
          <Link to={`/series/${hit.lecture.series}`} className="listen-text-link">
            看系列
          </Link>
        </div>
      </article>
    </li>
  );
}
