import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

export interface User {
  id: number;
  name: string;
  role: "merchandiser" | "supervisor";
  unit_id: number | null;
  unit_name?: string | null;
  lang: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (login: string, secret: string) => Promise<User>;
  signOut: () => void;
}

const Ctx = createContext<AuthState | null>(null);
const USER_KEY = "lt.user";

function cachedUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function cacheUser(u: User | null) {
  try {
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Start from the cached user so a supervisor opening the app offline still gets in.
  const [user, setUser] = useState<User | null>(() => (getToken() ? cachedUser() : null));
  const [loading, setLoading] = useState(() => !!getToken() && !cachedUser());

  useEffect(() => {
    if (!getToken()) return;
    api<{ user: User }>("/api/auth/me")
      .then((r) => {
        setUser(r.user);
        cacheUser(r.user);
      })
      .catch(() => {
        /* offline: keep cached user; 401 is handled by the signed-out event */
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onOut = () => {
      cacheUser(null);
      setUser(null);
    };
    window.addEventListener("lt:signed-out", onOut);
    return () => window.removeEventListener("lt:signed-out", onOut);
  }, []);

  const signIn = useCallback(async (login: string, secret: string) => {
    const r = await api<{ token: string; user: User }>("/api/auth/login", { body: { login, secret } });
    setToken(r.token);
    const me = await api<{ user: User }>("/api/auth/me");
    setUser(me.user);
    cacheUser(me.user);
    return me.user;
  }, []);

  const signOut = useCallback(() => {
    api("/api/auth/logout", { method: "POST" }).catch(() => {});
    setToken(null);
    cacheUser(null);
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, signIn, signOut }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
