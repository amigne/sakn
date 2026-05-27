import { Navigate } from "react-router-dom";
import { Spinner } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";

export default function AdminGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const isLoading = useAuthStore((s) => s.isLoading);
  const isInitialized = useAuthStore((s) => s.isInitialized);

  if (!isInitialized || isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user || user.role !== "administrator") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
