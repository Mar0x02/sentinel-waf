import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { authApi, setUnauthorizedHandler, TOKEN_STORAGE_KEY } from "../api/client";

interface AuthContextValue {
  loading: boolean;
  isAuthenticated: boolean;
  username: string | null;
  mustChangePassword: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  onPasswordChanged: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  function reset() {
    setIsAuthenticated(false);
    setUsername(null);
    setMustChangePassword(false);
  }

  useEffect(() => {
    setUnauthorizedHandler(reset);

    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((me) => {
        setIsAuthenticated(true);
        setUsername(me.username);
        setMustChangePassword(me.must_change_password);
      })
      .catch(() => reset())
      .finally(() => setLoading(false));
  }, []);

  async function login(user: string, password: string) {
    const result = await authApi.login(user, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setIsAuthenticated(true);
    setUsername(user);
    setMustChangePassword(result.must_change_password);
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    reset();
  }

  function onPasswordChanged() {
    setMustChangePassword(false);
  }

  return (
    <AuthContext.Provider value={{ loading, isAuthenticated, username, mustChangePassword, login, logout, onPasswordChanged }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
