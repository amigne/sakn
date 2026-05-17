import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AdminLayout from "@/components/admin/AdminLayout";
import { TextInput, Select, Badge, Pagination, Spinner } from "@/components/ui";
import { listUsers } from "@/services/admin";
import type { AdminUser } from "@/types/admin";

export default function AdminUsersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [offset, setOffset] = useState(0);
  const [sortField, setSortField] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const limit = 20;

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { offset, limit, sort: sortField, order: sortOrder };
      if (search) params.search = search;
      if (statusFilter !== "all") params.status = statusFilter;
      const data = await listUsers(params as never);
      setUsers(data.users);
      setTotal(data.pagination.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_load_users"));
    } finally {
      setLoading(false);
    }
  }, [offset, search, statusFilter, sortField, sortOrder, t]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
    setOffset(0);
  };

  const SortHeader = ({ field, children }: { field: string; children: React.ReactNode }) => (
    <th scope="col" onClick={() => handleSort(field)}
      className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase cursor-pointer hover:text-[var(--color-text)] select-none whitespace-nowrap">
      {children}{sortField === field ? (sortOrder === "asc" ? " ▴" : " ▾") : ""}
    </th>
  );

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const statusVariant = (s: string) => {
    if (s === "active") return "success";
    if (s === "blocked" || s === "locked") return "error";
    return "warning";
  };

  return (
    <AdminLayout title={t("admin.user_management")}>
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="flex-1 min-w-[200px]">
            <TextInput
              placeholder={t("admin.search_email")}
              value={search}
              onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            />
          </div>
          <Select
            options={[
              { value: "all", label: t("admin.all_status") },
              { value: "active", label: t("admin.active_status") },
              { value: "pending", label: t("admin.pending_status") },
              { value: "blocked", label: t("admin.blocked_status") },
              { value: "locked", label: t("admin.locked_status") },
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
                  <th scope="col" onClick={() => handleSort("name")}
                    className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase cursor-pointer hover:text-[var(--color-text)] select-none hidden md:table-cell">
                    {t("admin.name")}{sortField === "name" ? (sortOrder === "asc" ? " ▴" : " ▾") : ""}
                  </th>
                  <SortHeader field="email">{t("admin.email")}</SortHeader>
                  <SortHeader field="status">{t("admin.status")}</SortHeader>
                  <SortHeader field="role">{t("admin.role")}</SortHeader>
                  <SortHeader field="created_at">{t("admin.joined")}</SortHeader>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-20">{t("admin.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">{t("admin.no_users_found")}</td></tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                      <td className="px-3 py-2 text-[var(--color-text)] whitespace-nowrap hidden md:table-cell">{[user.first_name, user.last_name].filter(Boolean).join(" ") || "—"}</td>
                      <td className="px-3 py-2 font-mono text-[var(--color-text)]">{user.email}</td>
                      <td className="px-3 py-2"><Badge variant={statusVariant(user.status)}>{user.status}</Badge></td>
                      <td className="px-3 py-2 text-[var(--color-text)] capitalize">{user.role}</td>
                      <td className="px-3 py-2 text-[var(--color-text-secondary)]">{new Date(user.created_at).toLocaleDateString()}</td>
                      <td className="px-3 py-2">
                        <button onClick={() => navigate(`/admin/users/${user.id}`)} className="text-xs text-primary-600 hover:text-primary-700">{t("admin.view")}</button>
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
