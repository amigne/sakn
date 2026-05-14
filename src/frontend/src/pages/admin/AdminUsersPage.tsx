import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { TextInput, Select, Badge, Pagination } from "@/components/ui";
import type { AdminUser } from "@/types/admin";
import type { UserStatus, UserRole } from "@/types/user";

const mockUsers: AdminUser[] = Array.from({ length: 50 }, (_, i) => ({
  id: `user-${i + 1}`,
  email: `user${i + 1}@example.com`,
  role: (i === 0 ? "administrator" : i < 5 ? "authenticated" : "visitor") as UserRole,
  status: (i % 7 === 0 ? "blocked" : i % 11 === 0 ? "pending" : "active") as UserStatus,
  email_verified: i % 3 !== 0,
  failed_login_attempts: i % 5 === 0 ? 3 : 0,
  locked_until: i % 10 === 0 ? "2026-05-15T10:00:00Z" : null,
  admin_notes: i === 0 ? "Initial admin user" : null,
  created_at: new Date(2026, 0, 1 + i).toISOString(),
  updated_at: new Date(2026, 4, 1 + i).toISOString(),
})).reverse();

export default function AdminUsersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const filtered = useMemo(() => {
    let users = mockUsers;
    if (search) users = users.filter((u) => u.email.toLowerCase().includes(search.toLowerCase()));
    if (statusFilter !== "all") users = users.filter((u) => u.status === statusFilter);
    if (roleFilter !== "all") users = users.filter((u) => u.role === roleFilter);
    return users;
  }, [search, statusFilter, roleFilter]);

  const paged = filtered.slice(offset, offset + limit);

  const statusVariant = (s: string) => {
    if (s === "active") return "success";
    if (s === "blocked") return "error";
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
            options={[{ value: "all", label: "All Status" }, { value: "active", label: "Active" }, { value: "pending", label: "Pending" }, { value: "blocked", label: "Blocked" }]}
            value={statusFilter}
            onChange={(v) => { setStatusFilter(v); setOffset(0); }}
          />
          <Select
            options={[{ value: "all", label: "All Roles" }, { value: "visitor", label: "Visitor" }, { value: "authenticated", label: "User" }, { value: "administrator", label: "Admin" }]}
            value={roleFilter}
            onChange={(v) => { setRoleFilter(v); setOffset(0); }}
          />
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Email</th>
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Status</th>
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Joined</th>
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-20">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((user) => (
              <tr key={user.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                <td className="px-3 py-2 font-mono text-[var(--color-text)]">{user.email}</td>
                <td className="px-3 py-2"><Badge variant={statusVariant(user.status)}>{user.status}</Badge></td>
                <td className="px-3 py-2 text-[var(--color-text)] capitalize">{user.role}</td>
                <td className="px-3 py-2 text-[var(--color-text-secondary)]">{new Date(user.created_at).toLocaleDateString()}</td>
                <td className="px-3 py-2">
                  <button onClick={() => navigate(`/admin/users/${user.id}`)} className="text-xs text-primary-600 hover:text-primary-700">View</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4">
          <Pagination offset={offset} limit={limit} total={filtered.length} onChange={setOffset} />
        </div>
      </div>
    </AdminLayout>
  );
}
