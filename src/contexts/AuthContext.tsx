"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
} from "react";

import {
  authApi,
  clearTokens,
  getStoredTokens,
  storeTokens,
  ApiClientError,
} from "@/services/api";
import type {
  AuthState,
  LoginCredentials,
  RegisterPayload,
  User,
} from "@/types/auth";

type Action =
  | { type: "AUTH_INIT" }
  | { type: "AUTH_SUCCESS"; user: User }
  | { type: "AUTH_FAILURE" }
  | { type: "LOGOUT" };

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

function reducer(state: AuthState, action: Action): AuthState {
  switch (action.type) {
    case "AUTH_INIT":
      return { ...state, isLoading: true };
    case "AUTH_SUCCESS":
      return { user: action.user, isAuthenticated: true, isLoading: false };
    case "AUTH_FAILURE":
    case "LOGOUT":
      return { user: null, isAuthenticated: false, isLoading: false };
    default:
      return state;
  }
}

interface AuthContextValue extends AuthState {
  login: (creds: LoginCredentials) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Initialise – check existing tokens on mount
  useEffect(() => {
    const init = async () => {
      const tokens = getStoredTokens();
      if (!tokens?.access_token) {
        dispatch({ type: "AUTH_FAILURE" });
        return;
      }
      try {
        const user = await authApi.me();
        dispatch({ type: "AUTH_SUCCESS", user });
      } catch {
        clearTokens();
        dispatch({ type: "AUTH_FAILURE" });
      }
    };
    init();
  }, []);

  const setAuthCookie = (loggedIn: boolean) => {
    if (typeof document === "undefined") return;
    if (loggedIn) {
      document.cookie =
        "heat_wave_logged_in=true;path=/;max-age=604800;SameSite=Lax";
    } else {
      document.cookie = "heat_wave_logged_in=;path=/;max-age=0";
    }
  };

  const login = useCallback(async (creds: LoginCredentials) => {
    const tokens = await authApi.login(creds);
    storeTokens(tokens);
    setAuthCookie(true);
    const user = await authApi.me();
    dispatch({ type: "AUTH_SUCCESS", user });
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    await authApi.register(payload);
    const tokens = await authApi.login({
      email: payload.email,
      password: payload.password,
    });
    storeTokens(tokens);
    setAuthCookie(true);
    const user = await authApi.me();
    dispatch({ type: "AUTH_SUCCESS", user });
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setAuthCookie(false);
    dispatch({ type: "LOGOUT" });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, register, logout }),
    [state, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
