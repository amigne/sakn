import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { Badge, Button, Modal, Spinner } from "@/components/ui";
import {
  adminVerifyEmail,
  blockUser,
  deleteUser,
  demoteUser,
  getUser,
  getUserRateLimitStatus,
  lockUser,
  promoteUser,
  unblockUser,
  unlockUser,
  updateUserNotes,
} from "@/services/admin";
import { useAuthStore } from "@/stores/authStore";
import type { AdminUserDetail } from "@/types/admin";

export default function AdminUserDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [sessions, setSessions] = useState<
    { id: string; ip_address: string; user_agent: string; created_at: string; last_activity_at: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [rlStatus, setRlStatus] = useState<{
    soft_count: number;
    soft_limit: number;
    hard_count: number;
    hard_limit: number;
  } | null>(null);

  const isSelf = id === currentUserId;
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || "—";

  const fetchUser = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getUser(id);
      setUser(data.user);
      setSessions((data.sessions as never[]) || []);
      setNotes(data.user.admin_notes ?? "");
      // Fetch rate limit status
      try {
        const rl = await getUserRateLimitStatus(id);
        setRlStatus(rl);
      } catch {
        setRlStatus(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_load_user"));
    } finally {
      setLoading(false);
    }
  }, [id, t]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActing(true);
    try {
      switch (action) {
        case "block":
          await blockUser(id);
          break;
        case "unblock":
          await unblockUser(id);
          break;
        case "lock":
          await lockUser(id);
          break;
        case "unlock":
          await unlockUser(id);
          break;
        case "promote":
          await promoteUser(id);
          break;
        case "demote":
          await demoteUser(id);
          break;
        case "verify":
          await adminVerifyEmail(id);
          break;
        case "delete":
          await deleteUser(id);
          navigate("/admin/users");
          return;
      }
      await fetchUser();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_action_user", { action }));
    } finally {
      setActing(false);
      setConfirmAction(null);
    }
  };

  const handleSaveNotes = async () => {
    if (!id) return;
    setSavingNotes(true);
    try {
      await updateUserNotes(id, notes);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_save_notes"));
    } finally {
      setSavingNotes(false);
    }
  };

  if (loading)
    return (
      <AdminLayout title={t("admin.user_detail")}>
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  if (!user)
    return (
      <AdminLayout title={t("admin.user_detail")}>
        <p className="text-sm text-[var(--color-text-secondary)]">{error || t("admin.user_not_found")}</p>
      </AdminLayout>
    );

  const statusVariant = (s: string) => {
    if (s === "active") return "success";
    if (s === "blocked" || s === "locked") return "error";
    return "warning";
  };

  return (
    <AdminLayout title={`${t("admin.user_detail")}: ${user.email}`}>
      <div className="space-y-4 max-w-lg">
        {/* Info Card */}
        <div className="card p-4 space-y-2">
          <p className="text-sm text-[var(--color-text)]">
            <span className="font-medium">{t("admin.name")}:</span> {fullName}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("admin.status")}:</span>
            <Badge variant={statusVariant(user.status)}>{user.status}</Badge>
          </div>
          <p className="text-sm text-[var(--color-text)]">
            <span className="font-medium">{t("admin.role")}:</span> {user.role}
          </p>
          <p className="text-sm text-[var(--color-text)]">
            <span className="font-medium">{t("admin.email_verified")}</span>{" "}
            {user.email_verified ? t("common.yes") : t("common.no")}
            {!user.email_verified && !isSelf && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleAction("verify")}
                loading={acting}
                className="ms-2"
              >
                {t("admin.verify_now")}
              </Button>
            )}
          </p>
          <p className="text-sm text-[var(--color-text)]">
            <span className="font-medium">{t("admin.failed_login_attempts")}</span> {user.failed_login_attempts}
          </p>
          {user.locked_until && (
            <p className="text-sm text-[var(--color-text)]">
              <span className="font-medium">{t("admin.locked_until")}</span>{" "}
              {new Date(user.locked_until).toLocaleString()}
            </p>
          )}
          <p className="text-sm text-[var(--color-text-secondary)]">
            <span className="font-medium">{t("admin.created_at")}:</span> {new Date(user.created_at).toLocaleString()}
          </p>
          <p className="text-sm text-[var(--color-text-secondary)]">
            <span className="font-medium">{t("admin.last_updated")}:</span> {new Date(user.updated_at).toLocaleString()}
          </p>
        </div>

        {/* Actions */}
        {!isSelf && (
          <div className="card p-4 flex flex-wrap gap-2">
            {user.status === "blocked" ? (
              <Button variant="secondary" onClick={() => setConfirmAction("unblock")} disabled={acting}>
                {t("admin.unblock")}
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setConfirmAction("block")} disabled={acting}>
                {t("admin.block")}
              </Button>
            )}
            {user.status === "locked" ? (
              <Button variant="secondary" onClick={() => setConfirmAction("unlock")} disabled={acting}>
                {t("admin.unlock")}
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setConfirmAction("lock")} disabled={acting}>
                {t("admin.lock")}
              </Button>
            )}
            {user.role === "administrator" ? (
              <Button variant="secondary" onClick={() => setConfirmAction("demote")} disabled={acting}>
                {t("admin.demote_to_user")}
              </Button>
            ) : (
              <Button variant="primary" onClick={() => handleAction("promote")} loading={acting}>
                {t("admin.promote_to_admin")}
              </Button>
            )}
            <Button variant="danger" onClick={() => setConfirmAction("delete")} disabled={acting}>
              {t("admin.delete")}
            </Button>
          </div>
        )}

        {isSelf && (
          <div className="card p-4">
            <p className="text-sm text-[var(--color-text-secondary)]">{t("admin.self_modification_restricted")}</p>
          </div>
        )}

        {/* Rate Limit Status */}
        <div className="card p-4 space-y-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{t("admin.rate_limits_live")}</h3>
            <button
              onClick={async () => {
                if (!id) return;
                try {
                  const rl = await getUserRateLimitStatus(id);
                  setRlStatus(rl);
                } catch {}
              }}
              className="text-xs text-primary-600 hover:text-primary-700"
            >
              {t("admin.refresh")}
            </button>
          </div>
          {rlStatus ? (
            <>
              <p className="text-sm text-[var(--color-text)]">
                <span className="font-medium">{t("admin.soft_limit")}</span>{" "}
                <span className="font-mono">
                  {rlStatus.soft_count} / {rlStatus.soft_limit === 0 ? "∞" : rlStatus.soft_limit}
                </span>
                <span className="text-xs text-[var(--color-text-secondary)] ms-1">{t("admin.unit_req_s")}</span>
              </p>
              <p className="text-sm text-[var(--color-text)]">
                <span className="font-medium">{t("admin.hard_limit")}</span>{" "}
                <span className="font-mono">
                  {rlStatus.hard_count} / {rlStatus.hard_limit === 0 ? "∞" : rlStatus.hard_limit}
                </span>
                <span className="text-xs text-[var(--color-text-secondary)] ms-1">{t("admin.unit_req_h")}</span>
              </p>
            </>
          ) : (
            <p className="text-xs text-[var(--color-text-secondary)]">{t("admin.click_refresh_rate_limits")}</p>
          )}
        </div>

        {/* Admin Notes */}
        <div className="card p-4 space-y-2">
          <label className="text-sm font-medium text-[var(--color-text)]">{t("admin.admin_notes")}</label>
          <textarea
            className="w-full min-h-[80px] rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-sm text-[var(--color-text)]"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <Button variant="primary" onClick={handleSaveNotes} loading={savingNotes}>
            {t("admin.save_notes")}
          </Button>
        </div>

        {/* Sessions */}
        {sessions.length > 0 && (
          <div className="card p-4 space-y-2">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">
              {t("admin.active_sessions", { count: sessions.length })}
            </h3>
            {sessions.map((s) => (
              <div
                key={s.id}
                className="text-xs text-[var(--color-text-secondary)] border-b border-[var(--color-border)] pb-2"
              >
                <p>
                  <span className="font-medium">{t("admin.ip_label")}</span> {s.ip_address}
                </p>
                <p>
                  <span className="font-medium">{t("admin.agent")}</span> {s.user_agent}
                </p>
                <p>
                  <span className="font-medium">{t("admin.activity")}</span>{" "}
                  {new Date(s.last_activity_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        <Modal
          open={confirmAction !== null}
          onClose={() => setConfirmAction(null)}
          title={t("admin.confirm_action_title", { action: confirmAction || "" })}
        >
          <p className="text-sm text-[var(--color-text)] mb-4">
            {t("admin.confirm_action_message", { action: confirmAction || "", email: user.email })}
          </p>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={() => setConfirmAction(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant={confirmAction === "delete" ? "danger" : "primary"}
              onClick={() => confirmAction && handleAction(confirmAction)}
              loading={acting}
            >
              {t("admin.confirm")}
            </Button>
          </div>
        </Modal>
      </div>
    </AdminLayout>
  );
}
