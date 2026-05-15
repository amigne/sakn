import { useState, useEffect } from "react";
import PageLayout from "@/components/layout/PageLayout";
import { Button, Badge, Modal } from "@/components/ui";
import * as sessionService from "@/services/sessionService";
import type { Session } from "@/types/user";

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);

  const fetchSessions = async () => {
    setError(null);
    setLoading(true);
    try {
      const result = await sessionService.listSessions();
      setSessions(result.sessions);
    } catch {
      setError("Failed to load sessions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSessions(); }, []);

  const handleRevoke = async (id: string) => {
    try {
      await sessionService.revokeSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      setError("Failed to revoke session.");
    } finally {
      setRevokeTarget(null);
    }
  };

  const formatDate = (d: string) => {
    try { return new Date(d).toLocaleString(); } catch { return d; }
  };

  return (
    <PageLayout>
      <div className="max-w-2xl">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">Active Sessions</h1>

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        {loading ? (
          <p className="text-sm text-[var(--color-text-secondary)]">Loading...</p>
        ) : (
          <div className="card overflow-hidden">
            {sessions.length === 0 ? (
              <p className="p-4 text-sm text-[var(--color-text-secondary)]">No active sessions.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP Address</th>
                    <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Browser</th>
                    <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Last Activity</th>
                    <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Status</th>
                    <th scope="col" className="px-3 py-2 text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-20" />
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.id} className="border-b border-[var(--color-border)]">
                      <td className="px-3 py-2 font-mono text-[var(--color-text)]">{s.ip_address}</td>
                      <td className="px-3 py-2 text-[var(--color-text)] max-w-[200px] truncate" title={s.user_agent}>{s.user_agent?.split(" ").slice(0, 2).join(" ") || "—"}</td>
                      <td className="px-3 py-2 text-[var(--color-text-secondary)]">{formatDate(s.last_activity_at)}</td>
                      <td className="px-3 py-2">
                        {s.current ? <Badge variant="info">Current</Badge> : <span className="text-xs text-[var(--color-text-secondary)]">—</span>}
                      </td>
                      <td className="px-3 py-2">
                        {!s.current && (
                          <button onClick={() => setRevokeTarget(s.id)} className="text-xs text-error-600 hover:text-error-700">Revoke</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        <Modal
          open={!!revokeTarget}
          onClose={() => setRevokeTarget(null)}
          title="Revoke Session"
          footer={
            <>
              <Button variant="secondary" onClick={() => setRevokeTarget(null)}>Cancel</Button>
              <Button variant="danger" onClick={() => revokeTarget && handleRevoke(revokeTarget)}>Revoke</Button>
            </>
          }
        >
          <p>Are you sure you want to revoke this session? The device will be signed out immediately.</p>
        </Modal>
      </div>
    </PageLayout>
  );
}
