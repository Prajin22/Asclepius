"use client";

import type {
  DoctorApplication,
  PatientRegisterRequest,
  Role,
  TokenResponse,
  UserOut,
} from "@carebridge/shared-types";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DependencyList,
  type ReactNode,
} from "react";
import { ApiError, createApiClient, type ApiClient } from "./index";

export interface Session {
  token: string;
  user: UserOut;
  expiresAt: number;
}

/**
 * Session kept in this tab's sessionStorage. One app serves every role, so a tab
 * holds one account at a time; the API re-checks the role on every request.
 * See docs/SECURITY.md.
 */
export function createSessionStore(key: string) {
  return {
    read(): Session | null {
      try {
        const raw = window.sessionStorage.getItem(key);
        if (!raw) return null;
        const s = JSON.parse(raw) as Session;
        return s.expiresAt > Date.now() ? s : null;
      } catch {
        return null;
      }
    },
    write(s: Session) {
      try {
        window.sessionStorage.setItem(key, JSON.stringify(s));
      } catch {
        /* storage unavailable: session lives in memory only */
      }
    },
    clear() {
      try {
        window.sessionStorage.removeItem(key);
      } catch {
        /* ignore */
      }
    },
  };
}

interface AuthValue {
  session: Session | null;
  ready: boolean;
  api: ApiClient;
  login: (email: string, password: string) => Promise<Session>;
  /** Patient sign-up; signs the new account in. */
  register: (data: PatientRegisterRequest) => Promise<Session>;
  /** Doctor sign-up; signs the new, not-yet-approved account in. */
  applyAsDoctor: (data: DoctorApplication) => Promise<Session>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({
  children,
  baseUrl,
  storageKey,
  expectedRole,
}: {
  children: ReactNode;
  baseUrl: string;
  storageKey: string;
  /** Refuse any other kind of account. Omit when one app serves every role. */
  expectedRole?: Role;
}) {
  const store = useMemo(() => createSessionStore(storageKey), [storageKey]);
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const sessionRef = useRef<Session | null>(null);

  const logout = useCallback(() => {
    store.clear();
    sessionRef.current = null;
    setSession(null);
  }, [store]);

  const api = useMemo(
    () =>
      createApiClient({
        baseUrl,
        getToken: () => sessionRef.current?.token ?? null,
        onUnauthorized: logout,
      }),
    [baseUrl, logout],
  );

  useEffect(() => {
    const s = store.read();
    sessionRef.current = s;
    setSession(s);
    setReady(true);
  }, [store]);

  const start = useCallback(
    (r: TokenResponse) => {
      if (expectedRole && r.user.role !== expectedRole) throw new ApiError(403, "wrong_role", "Wrong account type");
      const s: Session = { token: r.access_token, user: r.user, expiresAt: Date.now() + r.expires_in * 1000 };
      store.write(s);
      sessionRef.current = s;
      setSession(s);
      return s;
    },
    [expectedRole, store],
  );

  const login = useCallback(
    async (email: string, password: string) => start(await api.auth.login(email, password)),
    [api, start],
  );
  const register = useCallback(
    async (data: PatientRegisterRequest) => start(await api.auth.registerPatient(data)),
    [api, start],
  );
  const applyAsDoctor = useCallback(
    async (data: DoctorApplication) => start(await api.auth.applyAsDoctor(data)),
    [api, start],
  );

  const value = useMemo(
    () => ({ session, ready, api, login, register, applyAsDoctor, logout }),
    [session, ready, api, login, register, applyAsDoctor, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function useApi(): ApiClient {
  return useAuth().api;
}

export interface QueryState<T> {
  data: T | undefined;
  error: ApiError | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (value: T) => void;
}

/** Tiny data-fetching hook: load on mount/deps change, expose reload. */
export function useQuery<T>(fetcher: (api: ApiClient) => Promise<T>, deps: DependencyList = []): QueryState<T> {
  const api = useApi();
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const seq = useRef(0);

  const reload = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    try {
      const result = await fetcherRef.current(api);
      if (id === seq.current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (id === seq.current) setError(e instanceof ApiError ? e : new ApiError(0, "generic", String(e)));
    } finally {
      if (id === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, ...deps]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** Calls `callback` every `intervalMs` while enabled and the tab is visible. */
export function usePolling(callback: () => unknown, intervalMs: number, enabled: boolean) {
  const ref = useRef(callback);
  ref.current = callback;
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void ref.current();
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
}

/** Maps an error to a localisation key under `errors.`. */
export function errorKey(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "generic";
  return `errors.${code}`;
}
