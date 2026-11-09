import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, { tokens } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  const loadMe = useCallback(async () => {
    const { data } = await api.get("/auth/me/");
    setUser(data);
    return data;
  }, []);

  useEffect(() => {
    (async () => {
      if (!tokens.access && !tokens.refresh) {
        setBooting(false);
        return;
      }
      try {
        await loadMe();
      } catch {
        tokens.clear();
        setUser(null);
      } finally {
        setBooting(false);
      }
    })();
  }, [loadMe]);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login/", { email, password });
    tokens.set({ access: data.access, refresh: data.refresh });
    const me = await loadMe();
    return me;
  }, [loadMe]);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout/");
    } catch {
      /* token may already be expired - ignore */
    }
    tokens.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      booting,
      login,
      logout,
      reload: loadMe,
      can: {
        managePeople: !!user?.permissions?.can_manage_people,
        approveLeave: !!user?.permissions?.can_approve_leave,
        admin: !!user?.permissions?.is_admin,
        manager: !!user?.permissions?.is_manager,
      },
    }),
    [user, booting, login, logout, loadMe]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
