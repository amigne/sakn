import { Routes, Route } from "react-router-dom";
// Tools
import PingPage from "@/pages/tools/PingPage";
import TraceroutePage from "@/pages/tools/TraceroutePage";
import DnsLookupPage from "@/pages/tools/DnsLookupPage";
import SslViewerPage from "@/pages/tools/SslViewerPage";
import NoToolsPage from "@/pages/tools/NoToolsPage";
import ToolGuard from "@/components/tool/ToolGuard";
import DefaultRedirect from "@/components/tool/DefaultRedirect";
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
import PrivacyPage from "@/pages/PrivacyPage";
// Admin
import AdminUsersPage from "@/pages/admin/AdminUsersPage";
import AdminUserDetailPage from "@/pages/admin/AdminUserDetailPage";
import AdminAccessPage from "@/pages/admin/AdminAccessPage";
import AdminRateLimitsPage from "@/pages/admin/AdminRateLimitsPage";
import AdminModulesPage from "@/pages/admin/AdminModulesPage";
import AdminSettingsPage from "@/pages/admin/AdminSettingsPage";
import AdminLogsPage from "@/pages/admin/AdminLogsPage";
import AdminGuard from "@/components/admin/AdminGuard";

export default function Router() {
  return (
    <Routes>
      {/* Tool routes — guarded by role permissions */}
      <Route path="/" element={<DefaultRedirect />} />
      <Route path="/ping" element={<ToolGuard toolName="ping"><PingPage /></ToolGuard>} />
      <Route path="/traceroute" element={<ToolGuard toolName="traceroute"><TraceroutePage /></ToolGuard>} />
      <Route path="/dns" element={<ToolGuard toolName="dns_lookup"><DnsLookupPage /></ToolGuard>} />
      <Route path="/ssl" element={<ToolGuard toolName="ssl_viewer"><SslViewerPage /></ToolGuard>} />
      <Route path="/no-tools" element={<NoToolsPage />} />

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

      {/* Legal */}
      <Route path="/privacy" element={<PrivacyPage />} />

      {/* Admin routes */}
      <Route path="/admin/users" element={<AdminGuard><AdminUsersPage /></AdminGuard>} />
      <Route path="/admin/users/:id" element={<AdminGuard><AdminUserDetailPage /></AdminGuard>} />
      <Route path="/admin/access" element={<AdminGuard><AdminAccessPage /></AdminGuard>} />
      <Route path="/admin/rate-limits" element={<AdminGuard><AdminRateLimitsPage /></AdminGuard>} />
      <Route path="/admin/modules" element={<AdminGuard><AdminModulesPage /></AdminGuard>} />
      <Route path="/admin/settings" element={<AdminGuard><AdminSettingsPage /></AdminGuard>} />
      <Route path="/admin/logs" element={<AdminGuard><AdminLogsPage /></AdminGuard>} />

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
