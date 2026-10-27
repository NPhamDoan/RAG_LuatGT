import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(password);
      navigate("/admin", { replace: true });
    } catch (err: any) {
      const status = err?.response?.status;
      setError(status === 401 ? "Mật khẩu không đúng." : "Đăng nhập thất bại. Thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-6"
      >
        <h1 className="mb-1 font-display text-lg font-bold">Đăng nhập quản trị</h1>
        <p className="mb-4 text-sm text-[var(--color-text-muted)]">
          Nhập mật khẩu để nạp/gỡ văn bản.
        </p>

        <label className="mb-1 block text-sm font-mono text-[var(--color-text-muted)]">
          Mật khẩu
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          className="mb-3 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          placeholder="••••••••"
        />

        {error && <p className="mb-3 text-sm text-[var(--color-danger,#e5484d)]">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password}
          className="w-full rounded-lg bg-[var(--color-accent)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </div>
  );
}
