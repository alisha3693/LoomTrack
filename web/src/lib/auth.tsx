import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

export interface User {
  id: number;
  name: string;
  role: "merchandiser" | "supervisor" | "buyer";
  unit_id: number | null;
  unit_name?: string | null;
  buyer_name?: string | null;
  must_change_secret?: number;
  /** 0 for a view-only buyer account; everyone else can make changes. */
  can_write?: number;
  lang: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (login: string, secret: string) => Promise<User>;
  signOut: () => void;
  refresh: () => Promise<void>;
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
  // Start from the cached user so a supervisor opening the app offline still gets in. The session itself is a cookie
  // the browser holds; if it has expired, the first request answers 401 and the app signs out.
  const [user, setUser] = useState<User | null>(() => cachedUser());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!cachedUser()) return;
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
    await api("/api/auth/login", { body: { login, secret } });
    const me = await api<{ user: User }>("/api/auth/me");
    setUser(me.user);
    cacheUser(me.user);
    return me.user;
  }, []);

  const signOut = useCallback(() => {
    api("/api/auth/logout", { method: "POST" }).catch(() => {});
    cacheUser(null);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    const me = await api<{ user: User }>("/api/auth/me");
    setUser(me.user);
    cacheUser(me.user);
  }, []);

  return <Ctx.Provider value={{ user, loading, signIn, signOut, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
