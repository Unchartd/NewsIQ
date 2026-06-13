/**
 * Zustand store for authentication state.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

import { clearAccessToken } from "@/lib/token-store";

export interface User {
  id: string;
  email: string;
  name: string | null;
  image_url: string | null;
  email_verified: boolean;
  role: "guest" | "user" | "premium" | "admin";
  subscription_plan: "free" | "pro" | "enterprise";
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
          isLoading: false,
        }),

      setLoading: (loading) => set({ isLoading: loading }),

      logout: () => {
        clearAccessToken();
        set({ user: null, isAuthenticated: false, isLoading: false });
      },
    }),
    {
      name: "newsiq-auth",
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
