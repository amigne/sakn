import { useState } from "react";
import PageLayout from "@/components/layout/PageLayout";
import { Button, Badge, Modal } from "@/components/ui";

interface MockSession {
  id: string;
  ip_address: string;
  user_agent: string;
  created_at: string;
  last_activity_at: string;
  current: boolean;
}

const mockSessions: MockSession[] = [
  { id: "1", ip_address: "203.0.113.1", user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0", created_at: "2026-05-14T08:00:00Z", last_activity_at: "2026-05-14T10:00:00Z", current: true },
  { id: "2", ip_address: "198.51.100.42", user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/18.0", created_at: "2026-05-13T14:30:00Z", last_activity_at: "2026-05-13T18:45:00Z", current: false },
  { id: "3", ip_address: "192.0.2.99", user_agent: "Mozilla/5.0 (X11; Linux x86_64) Firefox/134.0", created_at: "2026-05-12T09:15:00Z", last_activity_at: "2026-05-12T12:00:00Z", current: false },
];

export default function SessionsPage() {
  const [sessions, setSessions] = useState<MockSession[]>(mockSessions);
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);

  const handleRevoke = (id: string) => {
    setSessions(sessions.filter((s) => s.id !== id));
    setRevokeTarget(null);
  };

  const formatDate = (d: string) => {
    try { return new Date(d).toLocaleString(); } catch { return d; }
  };

  return (
    <PageLayout>
      <div className="max-w-2xl">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">Active Sessions</h1>

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
                    <td className="px-3 py-2 text-[var(--color-text)] max-w-[200px] truncate" title={s.user_agent}>{s.user_agent.split(" ").slice(0, 2).join(" ")}</td>
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
