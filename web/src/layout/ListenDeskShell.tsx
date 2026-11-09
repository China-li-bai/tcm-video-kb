import { FormEvent, useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useSearchParams } from "react-router-dom";

export function ListenDeskShell() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const needle = q.trim();
    navigate(needle ? `/search?q=${encodeURIComponent(needle)}` : "/search");
  }

  return (
    <div className="listen-desk">
      <header className="listen-topbar">
        <Link to="/" className="listen-brand" aria-label="人纪首页">
          <span className="listen-brand-mark">人纪</span>
        </Link>

        <form className="listen-search" onSubmit={onSearch} role="search">
          <span className="listen-search-icon" aria-hidden>
            ⌕
          </span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="别处听到的，查出处…"
            spellCheck={false}
            aria-label="搜索出处"
          />
        </form>

        <Link to="/" className="listen-top-link hide-sm">
          回首页
        </Link>
      </header>

      <main className="listen-main">
        <Outlet />
      </main>

      <nav className="listen-mob-nav" aria-label="底部导航">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "mob-item active" : "mob-item")}>
          <span className="mob-ico" aria-hidden>
            ◈
          </span>
          <span>听课</span>
        </NavLink>
        <NavLink to="/series" className={({ isActive }) => (isActive ? "mob-item active" : "mob-item")}>
          <span className="mob-ico" aria-hidden>
            ▤
          </span>
          <span>系列</span>
        </NavLink>
        <NavLink to="/stash" className={({ isActive }) => (isActive ? "mob-item active" : "mob-item")}>
          <span className="mob-ico" aria-hidden>
            ▣
          </span>
          <span>收获匣</span>
        </NavLink>
      </nav>
    </div>
  );
}
