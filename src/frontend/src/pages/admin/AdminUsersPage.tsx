import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { TextInput, Select, Badge, Pagination, Spinner } from "@/components/ui";
import { listUsers } from "@/services/admin";
import type { AdminUser } from "@/types/admin";

export default function AdminUsersPage() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { offset, limit };
      if (search) params.search = search;
      if (statusFilter !== "all") params.status = statusFilter;
      const data = await listUsers(params as never);
      setUsers(data.users);
      setTotal(data.pagination.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, [offset, search, statusFilter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const statusVariant = (s: string) => {
    if (s === "active") return "success";
    if (s === "blocked" || s === "locked") return "error";
    return "warning";
  };

  return (
    <AdminLayout title="User Management">
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="flex-1 min-w-[200px]">
            <TextInput
              placeholder="Search by email..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            />
          </div>
          <Select
            options={[
              { value: "all", label: "All Status" },
              { value: "active", label: "Active" },
              { value: "pending", label: "Pending" },
              { value: "blocked", label: "Blocked" },
              { value: "locked", label: "Locked" },
            ]}
            value={statusFilter}
            onChange={(v) => { setStatusFilter(v); setOffset(0); }}
          />
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase hidden md:table-cell">Name</th>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Email</th>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Status</th>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Joined</th>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-20">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No users found.</td></tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                      <td className="px-3 py-2 text-[var(--color-text)] whitespace-nowrap hidden md:table-cell">{[user.first_name, user.last_name].filter(Boolean).join(" ") || "—"}</td>
                      <td className="px-3 py-2 font-mono text-[var(--color-text)]">{user.email}</td>
                      <td className="px-3 py-2"><Badge variant={statusVariant(user.status)}>{user.status}</Badge></td>
                      <td className="px-3 py-2 text-[var(--color-text)] capitalize">{user.role}</td>
                      <td className="px-3 py-2 text-[var(--color-text-secondary)]">{new Date(user.created_at).toLocaleDateString()}</td>
                      <td className="px-3 py-2">
                        <button onClick={() => navigate(`/admin/users/${user.id}`)} className="text-xs text-primary-600 hover:text-primary-700">View</button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            <div className="mt-4">
              <Pagination offset={offset} limit={limit} total={total} onChange={setOffset} />
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
