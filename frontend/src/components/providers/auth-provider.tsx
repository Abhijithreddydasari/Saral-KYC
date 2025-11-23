"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, setAuthTokenProvider } from "@/lib/api-client";
import type { AuthResponse, User } from "@/types/auth";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (fullName: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = "saral-kyc-auth-token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setToken(stored);
    } else {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setAuthTokenProvider(token ? () => token : null);
    if (!token) {
      setUser(null);
      setLoading(false);
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(STORAGE_KEY);
      }
      return;
    }

    let cancelled = false;
    const fetchProfile = async () => {
      setLoading(true);
      try {
        const { data } = await apiClient.get<User>("/auth/me");
        if (!cancelled) {
          setUser(data);
        }
      } catch (error) {
        console.error("Failed to load profile", error);
        if (!cancelled) {
          setToken(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchProfile();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const persistToken = useCallback((nextToken: string | null) => {
    setToken(nextToken);
    if (typeof window === "undefined") return;
    if (nextToken) {
      window.localStorage.setItem(STORAGE_KEY, nextToken);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data } = await apiClient.post<AuthResponse>("/auth/login", { email, password });
      persistToken(data.token);
      setUser(data.user);
    },
    [persistToken],
  );

  const signup = useCallback(
    async (fullName: string, email: string, password: string) => {
      const { data } = await apiClient.post<AuthResponse>("/auth/signup", {
        full_name: fullName,
        email,
        password,
      });
      persistToken(data.token);
      setUser(data.user);
    },
    [persistToken],
  );

  const logout = useCallback(() => {
    persistToken(null);
    setUser(null);
  }, [persistToken]);

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    const { data } = await apiClient.get<User>("/auth/me");
    setUser(data);
  }, [token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      login,
      signup,
      logout,
      refreshProfile,
    }),
    [user, token, loading, login, signup, logout, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

