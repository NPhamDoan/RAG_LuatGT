import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

interface Props {
  activeJobCount?: number;
}

export default function AppLayout({ activeJobCount = 0 }: Props) {
  const { isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Nav */}
      <header className="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
        <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-4">
          <NavLink to="/" className="flex items-center gap-2 font-display font-bold text-base tracking-tight">
            <span className="text-[var(--color-accent)]">RAG</span>
            <span className="text-[var(--color-text-muted)]">/</span>
            <span>Giao Thông</span>
          </NavLink>

          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-mono transition-colors ${
                  isActive
                    ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                }`
              }
            >
              Tra cứu
            </NavLink>
            {isAdmin && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `relative rounded-lg px-3 py-1.5 text-sm font-mono transition-colors ${
                    isActive
                      ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`
                }
              >
                Quản lý
                {activeJobCount > 0 && (
                  <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--color-warning)] text-[10px] font-bold text-white">
                    {activeJobCount}
                  </span>
                )}
              </NavLink>
            )}
            {isAdmin ? (
              <button
                onClick={() => {
                  logout();
                  navigate("/");
                }}
                className="rounded-lg px-3 py-1.5 text-sm font-mono text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                Đăng xuất
              </button>
            ) : (
              <NavLink
                to="/login"
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-mono transition-colors ${
                    isActive
                      ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`
                }
              >
                Đăng nhập
              </NavLink>
            )}
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
