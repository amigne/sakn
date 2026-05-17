import { create } from "zustand";
import type { User, Preferences } from "@/types/user";
import * as authService from "@/services/authService";
import * as preferencesService from "@/services/preferencesService";

interface AuthState {
  user: User | null;
  preferences: Preferences | null;
  isLoading: boolean;
  isInitialized: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, passwordConfirm: string, firstName: string, lastName: string) => Promise<string>;
  updateProfile: (firstName: string, lastName: string) => Promise<void>;
  savePreferences: (updates: Record<string, string>) => Promise<void>;
  loadPreferences: () => Promise<void>;
  logout: () => Promise<void>;
  verifyEmail: (token: string) => Promise<string>;
  resendVerification: () => Promise<string>;
  requestPasswordReset: (email: string) => Promise<string>;
  resetPassword: (token: string, password: string, passwordConfirm: string) => Promise<string>;
  setUser: (user: User | null) => void;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  preferences: null,
  isLoading: false,
  isInitialized: false,

  setUser: (user) => set({ user }),

  init: async () => {
    if (get().isInitialized) return;
    set({ isLoading: true });
    try {
      const data = await authService.fetchCurrentUser();
      if (data) {
        set({ user: data });
      }
    } catch {
      // No active session — that's fine for visitor mode
    } finally {
      set({ isLoading: false, isInitialized: true });
    }
  },

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const result = await authService.login(email, password);
      set({ user: result.user });
      // Load and apply preferences from server after login
      await get().loadPreferences();
      // Apply theme from loaded preferences
      const prefs = get().preferences;
      if (prefs?.theme) {
        const { useThemeStore } = await import("@/stores/themeStore");
        useThemeStore.getState().setMode(prefs.theme);
      }
    } finally {
      set({ isLoading: false });
    }
  },

  register: async (email, password, passwordConfirm, firstName, lastName) => {
    set({ isLoading: true });
    try {
      const result = await authService.register({
        email,
        password,
        password_confirm: passwordConfirm,
        first_name: firstName,
        last_name: lastName,
      });
      return result.message;
    } finally {
      set({ isLoading: false });
    }
  },

  updateProfile: async (firstName, lastName) => {
    const result = await authService.updateProfile({
      first_name: firstName || null,
      last_name: lastName || null,
    });
    set({ user: result.user });
  },

  savePreferences: async (updates) => {
    try {
      const result = await preferencesService.updatePreferences(updates);
      set({ preferences: result.preferences });
    } catch {
      // silently fail
    }
  },

  loadPreferences: async () => {
    try {
      const result = await preferencesService.getPreferences();
      set({ preferences: result.preferences });
    } catch {
      // preferences not critical
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      await authService.logout();
    } catch {
      // Even if API call fails, clear local state
    } finally {
      set({ user: null, preferences: null, isLoading: false });
    }
  },

  verifyEmail: async (token) => {
    set({ isLoading: true });
    try {
      const result = await authService.verifyEmail(token);
      return result.message;
    } finally {
      set({ isLoading: false });
    }
  },

  resendVerification: async () => {
    set({ isLoading: true });
    try {
      const result = await authService.resendVerification();
      return result.message;
    } finally {
      set({ isLoading: false });
    }
  },

  requestPasswordReset: async (email) => {
    set({ isLoading: true });
    try {
      const result = await authService.requestPasswordReset(email);
      return result.message;
    } finally {
      set({ isLoading: false });
    }
  },

  resetPassword: async (token, password, passwordConfirm) => {
    set({ isLoading: true });
    try {
      const result = await authService.resetPassword(token, password, passwordConfirm);
      return result.message;
    } finally {
      set({ isLoading: false });
    }
  },
}));
