import { createContext, useContext, useState, type ReactNode } from "react";
import client, { getToken, setToken, clearToken } from "../api/client";

interface AuthContextValue {
  isAdmin: boolean;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải dùng trong <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAdmin, setIsAdmin] = useState<boolean>(() => !!getToken());

  const login = async (password: string) => {
    const { data } = await client.post("/api/auth/login", { password });
    setToken(data.token);
    setIsAdmin(true);
  };

  const logout = () => {
    clearToken();
    setIsAdmin(false);
  };

  return (
    <AuthContext.Provider value={{ isAdmin, login, logout }}>{children}</AuthContext.Provider>
  );
}
