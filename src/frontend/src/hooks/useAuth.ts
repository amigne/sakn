import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";

export function useAuth() {
  const store = useAuthStore();

  useEffect(() => {
    if (!store.isInitialized) {
      store.init();
    }
  }, []);

  return {
    user: store.user,
    isLoading: store.isLoading,
    isInitialized: store.isInitialized,
    isAuthenticated: store.user !== null,
    role: store.user?.role ?? "visitor",
    login: store.login,
    register: store.register,
    logout: store.logout,
    verifyEmail: store.verifyEmail,
    resendVerification: store.resendVerification,
    requestPasswordReset: store.requestPasswordReset,
    resetPassword: store.resetPassword,
  };
}
