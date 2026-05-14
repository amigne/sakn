import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { Button, Badge, Modal } from "@/components/ui";
import type { AdminUserDetail } from "@/types/admin";
import type { UserRole, UserStatus } from "@/types/user";

const mockUserDetail: Record<string, AdminUserDetail> = {
  "user-1": {
    id: "user-1",
    email: "admin@example.com",
    role: "administrator" as UserRole,
    status: "active" as UserStatus,
    email_verified: true,
    failed_login_attempts: 0,
    locked_until: null,
    admin_notes: "Initial admin user",
    created_at: "2026-01-15T10:00:00Z",
    updated_at: "2026-05-14T10:00:00Z",
    sessions: [
      { id: "s1", ip_address: "203.0.113.1", user_agent: "Chrome/131.0", created_at: "2026-05-14T08:00:00Z", last_activity_at: "2026-05-14T10:00:00Z" },
    ],
  },
};

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [user, setUser] = useState<AdminUserDetail | null>(mockUserDetail[id ?? ""] ?? null);
  const [notes, setNotes] = useState(user?.admin_notes ?? "");
  const [confirmAction, setConfirmAction] = useState<string | null>(null);

  if (!user) {
    return (
      <AdminLayout title="User Detail">
        <p className="text-sm text-[var(--color-text-secondary)]">User not found.</p>
      </AdminLayout>
    );
  }

  const handleAction = (action: string) => {
    if (action === "block") setUser({ ...user, status: "blocked" as UserStatus });
    else if (action === "unblock") setUser({ ...user, status: "active" as UserStatus });
    else if (action === "lock") setUser({ ...user, locked_until: "2026-05-15T10:00:00Z" });
    else if (action === "unlock") setUser({ ...user, locked_until: null });
    else if (action === "delete") { navigate("/admin/users"); return; }
    setConfirmAction(null);
  };

  const handleSaveNotes = () => {
    setUser({ ...user, admin_notes: notes });
  };

  const statusVariant = (s: string) => {
    if (s === "active") return "success";
    if (s === "blocked") return "error";
    return "warning";
  };

  return (
    <AdminLayout title="User Detail">
      <div className="space-y-4 max-w-2xl">
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-[var(--color-text)] mb-3">Info</h2>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-[var(--color-text-secondary)]">Email</dt><dd className="font-mono text-[var(--color-text)]">{user.email}</dd>
            <dt className="text-[var(--color-text-secondary)]">Role</dt><dd className="text-[var(--color-text)] capitalize">{user.role}</dd>
            <dt className="text-[var(--color-text-secondary)]">Status</dt><dd><Badge variant={statusVariant(user.status)}>{user.status}</Badge></dd>
            <dt className="text-[var(--color-text-secondary)]">Email Verified</dt><dd><Badge variant={user.email_verified ? "success" : "warning"}>{String(user.email_verified)}</Badge></dd>
            <dt className="text-[var(--color-text-secondary)]">Failed Logins</dt><dd className="text-[var(--color-text)]">{user.failed_login_attempts}</dd>
            <dt className="text-[var(--color-text-secondary)]">Locked Until</dt><dd className="text-[var(--color-text)]">{user.locked_until ? new Date(user.locked_until).toLocaleString() : "—"}</dd>
            <dt className="text-[var(--color-text-secondary)]">Joined</dt><dd className="text-[var(--color-text-secondary)]">{new Date(user.created_at).toLocaleDateString()}</dd>
            <dt className="text-[var(--color-text-secondary)]">Updated</dt><dd className="text-[var(--color-text-secondary)]">{new Date(user.updated_at).toLocaleDateString()}</dd>
          </dl>

          <div className="flex flex-wrap gap-2 mt-4">
            {user.status !== "blocked" ? (
              <Button variant="danger" size="sm" onClick={() => setConfirmAction("block")}>Block</Button>
            ) : (
              <Button variant="primary" size="sm" onClick={() => setConfirmAction("unblock")}>Unblock</Button>
            )}
            {user.locked_until ? (
              <Button variant="secondary" size="sm" onClick={() => setConfirmAction("unlock")}>Unlock</Button>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => setConfirmAction("lock")}>Lock</Button>
            )}
            {user.role !== "administrator" && (
              <Button variant="danger" size="sm" onClick={() => setConfirmAction("delete")}>Delete</Button>
            )}
          </div>
        </div>

        <div className="card p-4">
          <h2 className="text-sm font-semibold text-[var(--color-text)] mb-3">Admin Notes</h2>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <Button size="sm" className="mt-2" onClick={handleSaveNotes}>Save Notes</Button>
        </div>

        {user.sessions.length > 0 && (
          <div className="card p-4">
            <h2 className="text-sm font-semibold text-[var(--color-text)] mb-3">Active Sessions ({user.sessions.length})</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Browser</th>
                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {user.sessions.map((s) => (
                  <tr key={s.id} className="border-b border-[var(--color-border)]">
                    <td className="px-3 py-1 font-mono text-[var(--color-text)]">{s.ip_address}</td>
                    <td className="px-3 py-1 text-[var(--color-text)]">{s.user_agent}</td>
                    <td className="px-3 py-1 text-[var(--color-text-secondary)]">{new Date(s.last_activity_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Modal
          open={!!confirmAction}
          onClose={() => setConfirmAction(null)}
          title={`${confirmAction?.charAt(0).toUpperCase()}${confirmAction?.slice(1)} User`}
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmAction(null)}>Cancel</Button>
              <Button variant={confirmAction === "delete" ? "danger" : "primary"} onClick={() => confirmAction && handleAction(confirmAction)}>Confirm</Button>
            </>
          }
        >
          <p>Are you sure you want to {confirmAction} user <strong>{user.email}</strong>?</p>
        </Modal>
      </div>
    </AdminLayout>
  );
}
