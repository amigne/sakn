import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { Button, Badge, Modal, Spinner } from "@/components/ui";
import {
  getUser, blockUser, unblockUser, lockUser, unlockUser, deleteUser,
  updateUserNotes, promoteUser, demoteUser, adminVerifyEmail,
  getUserRateLimitStatus,
} from "@/services/admin";
import { useAuthStore } from "@/stores/authStore";
import type { AdminUserDetail } from "@/types/admin";

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [sessions, setSessions] = useState<{ id: string; ip_address: string; user_agent: string; created_at: string; last_activity_at: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [rlStatus, setRlStatus] = useState<{ soft_count: number; soft_limit: number; hard_count: number; hard_limit: number } | null>(null);

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
      } catch { setRlStatus(null); }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load user");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActing(true);
    try {
      switch (action) {
        case "block": await blockUser(id); break;
        case "unblock": await unblockUser(id); break;
        case "lock": await lockUser(id); break;
        case "unlock": await unlockUser(id); break;
        case "promote": await promoteUser(id); break;
        case "demote": await demoteUser(id); break;
        case "verify": await adminVerifyEmail(id); break;
        case "delete":
          await deleteUser(id);
          navigate("/admin/users");
          return;
      }
      await fetchUser();
    } catch (e) {
      setError(e instanceof Error ? e.message : `Failed to ${action} user`);
    } finally {
      setActing(false);
      setConfirmAction(null);
    }
  };

  const handleSaveNotes = async () => {
    if (!id) return;
    setSavingNotes(true);
    try { await updateUserNotes(id, notes); } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save notes");
    } finally { setSavingNotes(false); }
  };

  if (loading) return <AdminLayout title="User Detail"><div className="flex justify-center py-12"><Spinner /></div></AdminLayout>;
  if (!user) return <AdminLayout title="User Detail"><p className="text-sm text-[var(--color-text-secondary)]">{error || "User not found."}</p></AdminLayout>;

  const statusVariant = (s: string) => {
    if (s === "active") return "success";
    if (s === "blocked" || s === "locked") return "error";
    return "warning";
  };

  return (
    <AdminLayout title={`User: ${user.email}`}>
      <div className="space-y-4 max-w-lg">
        {/* Info Card */}
        <div className="card p-4 space-y-2">
          <p className="text-sm text-[var(--color-text)]"><span className="font-medium">Name:</span> {fullName}</p>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--color-text)]">Status:</span>
            <Badge variant={statusVariant(user.status)}>{user.status}</Badge>
          </div>
          <p className="text-sm text-[var(--color-text)]"><span className="font-medium">Role:</span> {user.role}</p>
          <p className="text-sm text-[var(--color-text)]">
            <span className="font-medium">Email verified:</span> {user.email_verified ? "Yes" : "No"}
            {!user.email_verified && !isSelf && (
              <Button variant="ghost" size="sm" onClick={() => handleAction("verify")} loading={acting} className="ml-2">Verify now</Button>
            )}
          </p>
          <p className="text-sm text-[var(--color-text)]"><span className="font-medium">Failed login attempts:</span> {user.failed_login_attempts}</p>
          {user.locked_until && <p className="text-sm text-[var(--color-text)]"><span className="font-medium">Locked until:</span> {new Date(user.locked_until).toLocaleString()}</p>}
          <p className="text-sm text-[var(--color-text-secondary)]"><span className="font-medium">Created:</span> {new Date(user.created_at).toLocaleString()}</p>
          <p className="text-sm text-[var(--color-text-secondary)]"><span className="font-medium">Updated:</span> {new Date(user.updated_at).toLocaleString()}</p>
        </div>

        {/* Actions */}
        {!isSelf && (
          <div className="card p-4 flex flex-wrap gap-2">
            {user.status === "blocked" ? (
              <Button variant="secondary" onClick={() => setConfirmAction("unblock")} disabled={acting}>Unblock</Button>
            ) : (
              <Button variant="secondary" onClick={() => setConfirmAction("block")} disabled={acting}>Block</Button>
            )}
            {user.status === "locked" ? (
              <Button variant="secondary" onClick={() => setConfirmAction("unlock")} disabled={acting}>Unlock</Button>
            ) : (
              <Button variant="secondary" onClick={() => setConfirmAction("lock")} disabled={acting}>Lock</Button>
            )}
            {user.role === "administrator" ? (
              <Button variant="secondary" onClick={() => setConfirmAction("demote")} disabled={acting}>Demote to User</Button>
            ) : (
              <Button variant="primary" onClick={() => handleAction("promote")} loading={acting}>Promote to Admin</Button>
            )}
            <Button variant="danger" onClick={() => setConfirmAction("delete")} disabled={acting}>Delete</Button>
          </div>
        )}

        {isSelf && (
          <div className="card p-4">
            <p className="text-sm text-[var(--color-text-secondary)]">This is your account. Self-modification is restricted.</p>
          </div>
        )}

        {/* Rate Limit Status */}
        <div className="card p-4 space-y-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">Rate Limits (live)</h3>
            <button
              onClick={async () => {
                if (!id) return;
                try { const rl = await getUserRateLimitStatus(id); setRlStatus(rl); } catch {}
              }}
              className="text-xs text-primary-600 hover:text-primary-700"
            >
              Refresh
            </button>
          </div>
          {rlStatus ? (
            <>
              <p className="text-sm text-[var(--color-text)]">
                <span className="font-medium">Soft limit:</span>{" "}
                <span className="font-mono">{rlStatus.soft_count} / {rlStatus.soft_limit === 0 ? "∞" : rlStatus.soft_limit}</span>
                <span className="text-xs text-[var(--color-text-secondary)] ml-1">(req/s)</span>
              </p>
              <p className="text-sm text-[var(--color-text)]">
                <span className="font-medium">Hard limit:</span>{" "}
                <span className="font-mono">{rlStatus.hard_count} / {rlStatus.hard_limit === 0 ? "∞" : rlStatus.hard_limit}</span>
                <span className="text-xs text-[var(--color-text-secondary)] ml-1">(req/h)</span>
              </p>
            </>
          ) : (
            <p className="text-xs text-[var(--color-text-secondary)]">Click Refresh to load rate limit counters.</p>
          )}
        </div>

        {/* Admin Notes */}
        <div className="card p-4 space-y-2">
          <label className="text-sm font-medium text-[var(--color-text)]">Admin Notes</label>
          <textarea className="w-full min-h-[80px] rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-sm text-[var(--color-text)]" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <Button variant="primary" onClick={handleSaveNotes} loading={savingNotes}>Save Notes</Button>
        </div>

        {/* Sessions */}
        {sessions.length > 0 && (
          <div className="card p-4 space-y-2">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">Active Sessions ({sessions.length})</h3>
            {sessions.map((s) => (
              <div key={s.id} className="text-xs text-[var(--color-text-secondary)] border-b border-[var(--color-border)] pb-2">
                <p><span className="font-medium">IP:</span> {s.ip_address}</p>
                <p><span className="font-medium">Agent:</span> {s.user_agent}</p>
                <p><span className="font-medium">Activity:</span> {new Date(s.last_activity_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        )}

        {error && <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>}

        <Modal open={confirmAction !== null} onClose={() => setConfirmAction(null)} title={`Confirm ${confirmAction}`}>
          <p className="text-sm text-[var(--color-text)] mb-4">Are you sure you want to {confirmAction} user {user.email}?</p>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={() => setConfirmAction(null)}>Cancel</Button>
            <Button variant={confirmAction === "delete" ? "danger" : "primary"} onClick={() => confirmAction && handleAction(confirmAction)} loading={acting}>Confirm</Button>
          </div>
        </Modal>
      </div>
    </AdminLayout>
  );
}
