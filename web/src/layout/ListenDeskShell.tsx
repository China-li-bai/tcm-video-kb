import { FormEvent, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";

const DESK_NAV = [
  { to: "/", label: "听课", end: true },
  { to: "/series", label: "系列", end: false },
  { to: "/stash", label: "收获匣", end: false },
] as const;

/** Shared learner chrome. Watch owns a locked viewport; other stages retain page scrolling. */
export function ListenDeskShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const isWatch = location.pathname.startsWith("/watch");
  const isTool =
    location.pathname === "/graph" || location.pathname === "/paths";

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const needle = q.trim();
    navigate(needle ? `/search?q=${encodeURIComponent(needle)}` : "/search");
  }

  const deskClass = [
    "listen-desk",
    isWatch ? "listen-desk--watch" : "",
    isTool ? "listen-desk--tool" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={deskClass}>
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

        <nav className="listen-desk-nav" aria-label="听课台导航">
          {DESK_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "desk-nav-link active" : "desk-nav-link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
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
