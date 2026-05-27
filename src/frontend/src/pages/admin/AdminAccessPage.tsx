import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import AdminLayout from "@/components/admin/AdminLayout";
import { Spinner, ToggleSwitch } from "@/components/ui";
import { listRolePermissions, updateRolePermissions } from "@/services/admin";
import type { AccessPermission } from "@/types/admin";
import { toolDisplayName } from "@/types/admin";

const ROLES = ["administrator", "authenticated", "visitor"];

export default function AdminAccessPage() {
  const { t } = useTranslation();
  const [permissions, setPermissions] = useState<AccessPermission[]>([]);
  const [tools, setTools] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchPermissions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listRolePermissions();
      setPermissions(data.permissions);
      const uniqueTools = [...new Set(data.permissions.map((p) => p.tool_name))].sort();
      setTools(uniqueTools);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_load_permissions"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchPermissions();
  }, [fetchPermissions]);

  const toggle = async (tool: string, role: string) => {
    const perm = permissions.find((p) => p.tool_name === tool && p.role === role);
    if (!perm) return;

    // Optimistic update
    const updated = permissions.map((p) =>
      p.tool_name === tool && p.role === role ? { ...p, allowed: !p.allowed } : p,
    );
    setPermissions(updated);

    setSaving(true);
    try {
      await updateRolePermissions([{ id: (perm as { id?: string }).id || "", allowed: !perm.allowed }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_update_permission"));
      // Revert on failure
      setPermissions(permissions);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout title={t("admin.access_rights")}>
      <div className="card p-4 max-w-md">
        <p className="text-sm text-[var(--color-text-secondary)] mb-4">{t("admin.access_description")}</p>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th
                  scope="col"
                  className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase"
                >
                  {t("admin.tool")}
                </th>
                {ROLES.map((r) => (
                  <th
                    key={r}
                    scope="col"
                    className="px-3 py-2 text-center text-xs font-semibold text-[var(--color-text-secondary)] uppercase capitalize"
                  >
                    {r}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tools.map((tool) => (
                <tr key={tool} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 font-medium text-[var(--color-text)] capitalize">{toolDisplayName(tool)}</td>
                  {ROLES.map((role) => {
                    const perm = permissions.find((p) => p.tool_name === tool && p.role === role);
                    return (
                      <td key={role} className="px-3 py-2">
                        <div className="flex justify-center">
                          <ToggleSwitch
                            checked={perm?.allowed ?? false}
                            onChange={() => toggle(tool, role)}
                            disabled={saving}
                          />
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </AdminLayout>
  );
}
