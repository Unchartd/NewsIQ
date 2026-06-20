import { create } from "zustand";

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthState {
  user: AdminUser | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: AdminUser, token: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,

  login: (user, token) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("newsiq_admin_token", token);
      localStorage.setItem("newsiq_admin_user", JSON.stringify(user));
    }
    set({ user, token, isAuthenticated: true });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("newsiq_admin_token");
      localStorage.removeItem("newsiq_admin_user");
    }
    set({ user: null, token: null, isAuthenticated: false });
  },

  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("newsiq_admin_token");
    const userRaw = localStorage.getItem("newsiq_admin_user");
    if (token && userRaw) {
      try {
        const user = JSON.parse(userRaw) as AdminUser;
        set({ user, token, isAuthenticated: true });
      } catch {
        // malformed stored data — clear it
        localStorage.removeItem("newsiq_admin_token");
        localStorage.removeItem("newsiq_admin_user");
      }
    }
  },
}));
