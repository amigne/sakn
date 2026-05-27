import { Route, Routes } from "react-router-dom";
import AdminGuard from "@/components/admin/AdminGuard";
import DefaultRedirect from "@/components/tool/DefaultRedirect";
import ToolGuard from "@/components/tool/ToolGuard";
import AccountDeletePage from "@/pages/account/AccountDeletePage";
// Account
import ProfilePage from "@/pages/account/ProfilePage";
import SessionsPage from "@/pages/account/SessionsPage";
import AdminAccessPage from "@/pages/admin/AdminAccessPage";
import AdminLogsPage from "@/pages/admin/AdminLogsPage";
import AdminModulesPage from "@/pages/admin/AdminModulesPage";
import AdminRateLimitsPage from "@/pages/admin/AdminRateLimitsPage";
import AdminSettingsPage from "@/pages/admin/AdminSettingsPage";
import AdminUserDetailPage from "@/pages/admin/AdminUserDetailPage";
// Admin
import AdminUsersPage from "@/pages/admin/AdminUsersPage";
// Auth
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import ResetPasswordPage from "@/pages/auth/ResetPasswordPage";
import VerifyEmailPage from "@/pages/auth/VerifyEmailPage";
import VerifyEmailSentPage from "@/pages/auth/VerifyEmailSentPage";
import NotFoundPage from "@/pages/NotFoundPage";
import PrivacyPage from "@/pages/PrivacyPage";
import DnsLookupPage from "@/pages/tools/DnsLookupPage";
import NoToolsPage from "@/pages/tools/NoToolsPage";
// Tools
import PingPage from "@/pages/tools/PingPage";
import SslViewerPage from "@/pages/tools/SslViewerPage";
import TraceroutePage from "@/pages/tools/TraceroutePage";

export default function Router() {
  return (
    <Routes>
      {/* Tool routes — guarded by role permissions */}
      <Route path="/" element={<DefaultRedirect />} />
      <Route
        path="/ping"
        element={
          <ToolGuard toolName="ping">
            <PingPage />
          </ToolGuard>
        }
      />
      <Route
        path="/traceroute"
        element={
          <ToolGuard toolName="traceroute">
            <TraceroutePage />
          </ToolGuard>
        }
      />
      <Route
        path="/dns"
        element={
          <ToolGuard toolName="dns_lookup">
            <DnsLookupPage />
          </ToolGuard>
        }
      />
      <Route
        path="/ssl"
        element={
          <ToolGuard toolName="ssl_viewer">
            <SslViewerPage />
          </ToolGuard>
        }
      />
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
      <Route
        path="/admin/users"
        element={
          <AdminGuard>
            <AdminUsersPage />
          </AdminGuard>
        }
      />
      <Route
        path="/admin/users/:id"
        element={
          <AdminGuard>
            <AdminUserDetailPage />
          </AdminGuard>
        }
      />
      <Route
        path="/admin/access"
        element={
          <AdminGuard>
            <AdminAccessPage />
          </AdminGuard>
        }
      />
      <Route
        path="/admin/rate-limits"
        element={
          <AdminGuard>
            <AdminRateLimitsPage />
          </AdminGuard>
        }
      />
      <Route
        path="/admin/modules"
        element={
          <AdminGuard>
            <AdminModulesPage />
          </AdminGuard>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <AdminGuard>
            <AdminSettingsPage />
          </AdminGuard>
        }
      />
      <Route
        path="/admin/logs"
        element={
          <AdminGuard>
            <AdminLogsPage />
          </AdminGuard>
        }
      />

      {/* 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
