import { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import ToggleSwitch from "@/components/ui/ToggleSwitch";
import type { AccessPermission } from "@/types/admin";

const tools = ["ping", "traceroute", "dns_lookup", "ssl_viewer"];
const roles = ["administrator", "authenticated", "visitor"];

function makeMock(): AccessPermission[] {
  return [
    { tool_name: "ping", role: "administrator", allowed: true },
    { tool_name: "ping", role: "authenticated", allowed: true },
    { tool_name: "ping", role: "visitor", allowed: true },
    { tool_name: "traceroute", role: "administrator", allowed: true },
    { tool_name: "traceroute", role: "authenticated", allowed: true },
    { tool_name: "traceroute", role: "visitor", allowed: false },
    { tool_name: "dns_lookup", role: "administrator", allowed: true },
    { tool_name: "dns_lookup", role: "authenticated", allowed: true },
    { tool_name: "dns_lookup", role: "visitor", allowed: true },
    { tool_name: "ssl_viewer", role: "administrator", allowed: true },
    { tool_name: "ssl_viewer", role: "authenticated", allowed: true },
    { tool_name: "ssl_viewer", role: "visitor", allowed: true },
  ];
}

export default function AdminAccessPage() {
  const [permissions, setPermissions] = useState<AccessPermission[]>(makeMock());
  const [saved, setSaved] = useState(false);

  const toggle = (tool: string, role: string) => {
    setPermissions((prev) =>
      prev.map((p) =>
        p.tool_name === tool && p.role === role ? { ...p, allowed: !p.allowed } : p
      )
    );
    setSaved(false);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <AdminLayout title="Access Rights">
      <div className="card p-4 max-w-md">
        <p className="text-sm text-[var(--color-text-secondary)] mb-4">
          Toggle tool access per role. Changes take effect immediately.
        </p>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
              {roles.map((r) => (
                <th key={r} scope="col" className="px-3 py-2 text-center text-xs font-semibold text-[var(--color-text-secondary)] uppercase capitalize">{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => (
              <tr key={tool} className="border-b border-[var(--color-border)]">
                <td className="px-3 py-2 font-medium text-[var(--color-text)] capitalize">{tool.replace("_", " ")}</td>
                {roles.map((role) => {
                  const perm = permissions.find((p) => p.tool_name === tool && p.role === role);
                  return (
                    <td key={role} className="px-3 py-2 text-center">
                      <ToggleSwitch
                        checked={perm?.allowed ?? false}
                        onChange={() => toggle(tool, role)}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>

        <button onClick={handleSave} className="mt-4 text-sm text-primary-600 hover:text-primary-700">
          {saved ? "Saved" : "Save Changes"}
        </button>
      </div>
    </AdminLayout>
  );
}
