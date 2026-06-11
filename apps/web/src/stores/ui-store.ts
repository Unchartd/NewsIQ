/**
 * Zustand store for global UI state: theme, filters, sidebar.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  // Sidebar
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // Active category filter
  activeCategory: string | null;
  setActiveCategory: (slug: string | null) => void;

  // Active location filter
  activeCountry: string | null;
  activeState: string | null;
  activeCity: string | null;
  setLocation: (country: string | null, state?: string | null, city?: string | null) => void;

  // Summary preference
  preferredSummary: "one_line" | "short" | "detailed";
  setPreferredSummary: (type: "one_line" | "short" | "detailed") => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // Sidebar
      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      // Category
      activeCategory: null,
      setActiveCategory: (slug) => set({ activeCategory: slug }),

      // Location
      activeCountry: null,
      activeState: null,
      activeCity: null,
      setLocation: (country, state = null, city = null) =>
        set({ activeCountry: country, activeState: state, activeCity: city }),

      // Summary
      preferredSummary: "short",
      setPreferredSummary: (type) => set({ preferredSummary: type }),
    }),
    {
      name: "newsiq-ui",
    }
  )
);
