import { Routes, Route, Navigate } from "react-router-dom";
// Tools
import PingPage from "@/pages/tools/PingPage";
import TraceroutePage from "@/pages/tools/TraceroutePage";
import DnsLookupPage from "@/pages/tools/DnsLookupPage";
import SslViewerPage from "@/pages/tools/SslViewerPage";
// Auth
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import VerifyEmailPage from "@/pages/auth/VerifyEmailPage";
import VerifyEmailSentPage from "@/pages/auth/VerifyEmailSentPage";
import ResetPasswordPage from "@/pages/auth/ResetPasswordPage";
// Account
import ProfilePage from "@/pages/account/ProfilePage";
import SessionsPage from "@/pages/account/SessionsPage";
import AccountDeletePage from "@/pages/account/AccountDeletePage";
// Admin
import AdminUsersPage from "@/pages/admin/AdminUsersPage";
import AdminUserDetailPage from "@/pages/admin/AdminUserDetailPage";
import AdminAccessPage from "@/pages/admin/AdminAccessPage";
import AdminRateLimitsPage from "@/pages/admin/AdminRateLimitsPage";
import AdminModulesPage from "@/pages/admin/AdminModulesPage";
import AdminSettingsPage from "@/pages/admin/AdminSettingsPage";
import AdminLogsPage from "@/pages/admin/AdminLogsPage";

export default function Router() {
  return (
    <Routes>
      {/* Tool routes */}
      <Route path="/" element={<Navigate to="/ping" replace />} />
      <Route path="/ping" element={<PingPage />} />
      <Route path="/traceroute" element={<TraceroutePage />} />
      <Route path="/dns" element={<DnsLookupPage />} />
      <Route path="/ssl" element={<SslViewerPage />} />

      {/* Auth routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/verify-email-sent" element={<VerifyEmailSentPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Account routes */}
      <Route path="/account/preferences" element={<ProfilePage />} />
      <Route path="/account/sessions" element={<SessionsPage />} />
      <Route path="/account/delete" element={<AccountDeletePage />} />

      {/* Admin routes */}
      <Route path="/admin/users" element={<AdminUsersPage />} />
      <Route path="/admin/users/:id" element={<AdminUserDetailPage />} />
      <Route path="/admin/access" element={<AdminAccessPage />} />
      <Route path="/admin/rate-limits" element={<AdminRateLimitsPage />} />
      <Route path="/admin/modules" element={<AdminModulesPage />} />
      <Route path="/admin/settings" element={<AdminSettingsPage />} />
      <Route path="/admin/logs" element={<AdminLogsPage />} />

      {/* 404 */}
      <Route path="*" element={
        <div className="flex h-screen items-center justify-center">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-[var(--color-text)]">404</h1>
            <p className="mt-2 text-[var(--color-text-secondary)]">Page not found.</p>
          </div>
        </div>
      } />
    </Routes>
  );
}
