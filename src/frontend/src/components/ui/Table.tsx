import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render?: (item: T) => ReactNode;
  className?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  sortBy?: string | null;
  sortDir?: "asc" | "desc";
  onSort?: (key: string) => void;
  emptyMessage?: string;
  rowKey: (item: T) => string;
  onRowClick?: (item: T) => void;
}

export default function Table<T>({
  columns,
  data,
  sortBy,
  sortDir,
  onSort,
  emptyMessage,
  rowKey,
  onRowClick,
}: TableProps<T>) {
  const { t } = useTranslation();
  const displayEmpty = emptyMessage ?? t("common.no_data");

  if (data.length === 0) {
    return <p className="py-8 text-center text-sm text-[var(--color-text-secondary)]">{displayEmpty}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={`px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide ${col.className ?? ""}`}
              >
                {col.sortable && onSort ? (
                  <button
                    className="flex items-center gap-1 hover:text-[var(--color-text)]"
                    onClick={() => onSort(col.key)}
                  >
                    {col.header}
                    {sortBy === col.key && (
                      <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        {sortDir === "asc" ? (
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                        ) : (
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        )}
                      </svg>
                    )}
                  </button>
                ) : (
                  col.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr
              key={rowKey(item)}
              className={`border-b border-[var(--color-border)] ${onRowClick ? "cursor-pointer hover:bg-[var(--color-surface-alt)]" : ""}`}
              onClick={onRowClick ? () => onRowClick(item) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-3 py-2 text-[var(--color-text)] ${col.className ?? ""}`}>
                  {col.render ? col.render(item) : String((item as Record<string, unknown>)[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
