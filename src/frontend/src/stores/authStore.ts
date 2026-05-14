import { create } from "zustand";
import type { User, UserRole } from "@/types/user";

interface AuthState {
  user: User | null;
  isLoading: boolean;

  // Mock setters
  setUser: (user: User | null) => void;
  setRole: (role: UserRole) => void;
  logout: () => void;

  // Dev toolbar
  devRole: UserRole | null;
  setDevRole: (role: UserRole | null) => void;
  getEffectiveUser: () => User | null;
  getEffectiveRole: () => UserRole;
}

const mockUser: User = {
  id: "0193c8d4-0000-7000-8000-000000000001",
  email: "user@sakn.local",
  role: "authenticated",
  status: "active",
  email_verified: true,
  locale: "fr-FR",
  created_at: "2026-05-14T10:00:00Z",
};

const mockAdmin: User = {
  id: "0193c8d4-0000-7000-8000-000000000000",
  email: "admin@sakn.local",
  role: "administrator",
  status: "active",
  email_verified: true,
  locale: "en-US",
  created_at: "2026-05-14T08:00:00Z",
};

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: false,
  devRole: null,

  setUser: (user) => set({ user }),

  setRole: (role) => {
    const { user } = get();
    if (user) {
      set({ user: { ...user, role } });
    }
  },

  logout: () => set({ user: null }),

  setDevRole: (devRole) => {
    if (devRole === null) {
      set({ devRole: null });
      return;
    }
    if (devRole === "visitor") {
      set({ devRole: "visitor" });
    } else if (devRole === "authenticated") {
      set({ devRole: "authenticated", user: mockUser });
    } else if (devRole === "administrator") {
      set({ devRole: "administrator", user: mockAdmin });
    }
  },

  getEffectiveUser: () => {
    const { user, devRole } = get();
    if (devRole === "visitor") return null;
    return user;
  },

  getEffectiveRole: () => {
    const { user, devRole } = get();
    if (devRole === "visitor") return "visitor";
    if (devRole === "administrator") return "administrator";
    if (devRole === "authenticated") return "authenticated";
    return user?.role ?? "visitor";
  },
}));
