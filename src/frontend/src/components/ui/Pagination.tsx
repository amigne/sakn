import { useTranslation } from "react-i18next";

interface PaginationProps {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}

export default function Pagination({ offset, limit, total, onChange }: PaginationProps) {
  const { t } = useTranslation();
  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  if (totalPages <= 1) return null;

  const pages: number[] = [];
  const maxVisible = 5;
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  const end = Math.min(totalPages, start + maxVisible - 1);
  start = Math.max(1, end - maxVisible + 1);
  for (let i = start; i <= end; i++) pages.push(i);

  const startIndex = offset + 1;
  const endIndex = Math.min(offset + limit, total);

  return (
    <nav className="flex items-center justify-between text-sm" aria-label={t("common.pagination")}>
      <span className="text-[var(--color-text-secondary)]">
        {t("common.page_info", { start: startIndex, end: endIndex, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={offset === 0}
          className="focus-ring rounded px-2 py-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text)] disabled:opacity-40"
          aria-label={t("common.previous_page")}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        {start > 1 && (
          <>
            <button onClick={() => onChange(0)} className="focus-ring rounded px-2 py-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">1</button>
            {start > 2 && <span className="px-1 text-[var(--color-text-secondary)]">...</span>}
          </>
        )}
        {pages.map((p) => (
          <button
            key={p}
            onClick={() => onChange((p - 1) * limit)}
            className={`focus-ring rounded px-2 py-1 ${
              p === currentPage
                ? "bg-primary-600 text-white"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
            }`}
            aria-current={p === currentPage ? "page" : undefined}
          >
            {p}
          </button>
        ))}
        {end < totalPages && (
          <>
            {end < totalPages - 1 && <span className="px-1 text-[var(--color-text-secondary)]">...</span>}
            <button onClick={() => onChange((totalPages - 1) * limit)} className="focus-ring rounded px-2 py-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">{totalPages}</button>
          </>
        )}
        <button
          onClick={() => onChange(offset + limit)}
          disabled={offset + limit >= total}
          className="focus-ring rounded px-2 py-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text)] disabled:opacity-40"
          aria-label={t("common.next_page")}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </nav>
  );
}
