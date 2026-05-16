import { NavLink } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useAvailableTools } from "@/hooks/useAvailableTools";

interface SidebarItem {
  label: string;
  to: string;
  icon: string;
  name: string;
}

const ALL_TOOLS: SidebarItem[] = [
  { label: "Ping", to: "/ping", name: "ping", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
  { label: "Traceroute", to: "/traceroute", name: "traceroute", icon: "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" },
  { label: "DNS", to: "/dns", name: "dns_lookup", icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" },
  { label: "TLS", to: "/ssl", name: "ssl_viewer", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
];

interface SidebarProps {
  collapsed?: boolean;
  onNavigate?: () => void;
  onToggle?: () => void;
  showToggle?: boolean;
}

export default function Sidebar({ collapsed = false, onNavigate, onToggle, showToggle = false }: SidebarProps) {
  const user = useAuthStore((s) => s.user);
  const role = user?.role ?? "visitor";
  const { tools: toolNames, checked } = useAvailableTools();
  const availableNames = checked ? new Set(toolNames) : null;
  const visibleTools = availableNames === null ? [] : ALL_TOOLS.filter(t => availableNames.has(t.name));

  return (
    <nav
      className={`flex shrink-0 flex-col border-e border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 py-2 transition-all duration-200 ${collapsed ? "w-14" : "w-48"}`}
    >
      {showToggle && onToggle && (
        <button
          onClick={onToggle}
          className={`mx-2 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${collapsed ? "justify-center" : ""}`}
          aria-label="Toggle sidebar"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
          {!collapsed && "Minimize menu"}
        </button>
      )}
      {!collapsed && (
        <div className="px-3 py-1 text-xs font-semibold uppercase text-gray-500 tracking-wide">
          Tools
        </div>
      )}
      {visibleTools.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={onNavigate}
          title={collapsed ? item.label : undefined}
          className={({ isActive }) =>
            `mx-2 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
              collapsed ? "justify-center" : ""
            } ${
              isActive
                ? "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400"
                : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
            }`
          }
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
          </svg>
          {!collapsed && item.label}
        </NavLink>
      ))}

      {role === "administrator" && (
        <>
          <div className="flex-1" />
          <hr className="mx-3 my-2 border-gray-200 dark:border-gray-700" />
          {!collapsed && (
            <div className="px-3 py-1 text-xs font-semibold uppercase text-gray-500 tracking-wide">
              Administration
            </div>
          )}
          <NavLink
            to="/admin/users"
            onClick={onNavigate}
            title={collapsed ? "Admin" : undefined}
            className={({ isActive }) =>
              `mx-2 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
                collapsed ? "justify-center" : ""
              } ${
                isActive
                  ? "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400"
                  : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`
            }
          >
            <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {!collapsed && "Admin"}
          </NavLink>
        </>
      )}
    </nav>
  );
}
