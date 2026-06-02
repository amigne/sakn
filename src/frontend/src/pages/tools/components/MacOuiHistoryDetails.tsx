import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { MacOuiHistoryEntry } from "@/api/tools/macOui";
import { Spinner } from "@/components/ui";

interface MacOuiHistoryDetailsProps {
  history: MacOuiHistoryEntry[];
  /** Callback for loading more history (wired in Sprint 5). */
  loadMoreHistory?: (offset: number, limit: number) => Promise<MacOuiHistoryEntry[]>;
  /** The date of the first sync deployment (wired in Sprint 5). */
  deployedSince?: string | null;
}

const CHANGE_TYPE_LABELS: Record<string, string> = {
  name_change: "tools.mac_oui.history_change_name_change",
  address_change: "tools.mac_oui.history_change_address_change",
  revoked: "tools.mac_oui.history_change_revoked",
};

export default function MacOuiHistoryDetails({ history, loadMoreHistory, deployedSince }: MacOuiHistoryDetailsProps) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<MacOuiHistoryEntry[]>(history);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(!!loadMoreHistory);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const offsetRef = useRef(history.length);

  // Sync with initial history prop on first render
  useEffect(() => {
    setEntries(history);
    offsetRef.current = history.length;
  }, [history]);

  const loadMore = useCallback(async () => {
    if (!loadMoreHistory || loading) return;
    setLoading(true);
    try {
      const more = await loadMoreHistory(offsetRef.current, 10);
      if (more.length === 0) {
        setHasMore(false);
      } else {
        setEntries((prev) => [...prev, ...more]);
        offsetRef.current += more.length;
      }
    } catch {
      // Silently fail — user can retry by scrolling again.
    } finally {
      setLoading(false);
    }
  }, [loadMoreHistory, loading]);

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    if (!loadMoreHistory) return;
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting && hasMore && !loading) {
          loadMore();
        }
      },
      { rootMargin: "0px 0px 200px 0px" },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMoreHistory, hasMore, loading, loadMore]);

  // Use the actual deployment date if available, otherwise fallback to today.
  const sinceDate = deployedSince ?? new Date().toISOString().slice(0, 10);

  const renderChangeLabel = (type: string): string => {
    const key = CHANGE_TYPE_LABELS[type];
    return key ? t(key) : type;
  };

  if (entries.length === 0) return null;

  return (
    <div className="mt-2 border-t border-[var(--color-border)] pt-2">
      <h4 className="mb-2 text-xs font-semibold text-[var(--color-text-secondary)] uppercase">
        {t("tools.mac_oui.history_title")}
      </h4>
      <p className="mb-2 text-xs text-[var(--color-text-secondary)]">
        {t("tools.mac_oui.history_since", { date: sinceDate })}
      </p>

      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th scope="col" className="px-2 py-1 text-start text-[var(--color-text-secondary)]">
                {t("tools.mac_oui.history_type")}
              </th>
              <th scope="col" className="px-2 py-1 text-start text-[var(--color-text-secondary)]">
                {t("tools.mac_oui.history_previous")}
              </th>
              <th scope="col" className="px-2 py-1 text-start text-[var(--color-text-secondary)]">
                {t("tools.mac_oui.history_new")}
              </th>
              <th scope="col" className="px-2 py-1 text-start text-[var(--color-text-secondary)]">
                {t("tools.mac_oui.history_date")}
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => (
              <tr key={`${entry.detected_at}-${i}`} className="border-b border-[var(--color-border)]">
                <td className="px-2 py-1 text-[var(--color-text)]">{renderChangeLabel(entry.change_type)}</td>
                <td
                  className="px-2 py-1 text-[var(--color-text)] max-w-48 truncate"
                  title={entry.previous_organization}
                >
                  {entry.previous_organization}
                </td>
                <td className="px-2 py-1 text-[var(--color-text)] max-w-48 truncate" title={entry.new_organization}>
                  {entry.new_organization}
                </td>
                <td className="px-2 py-1 whitespace-nowrap text-[var(--color-text-secondary)] font-mono">
                  {entry.detected_at.slice(0, 10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Sentinel for infinite scroll intersection observer */}
        {loadMoreHistory && <div ref={sentinelRef} className="h-1" />}

        {loading && (
          <div className="flex items-center justify-center gap-2 py-2 text-xs text-[var(--color-text-secondary)]">
            <Spinner size="sm" />
            <span>{t("tools.mac_oui.history_loading")}</span>
          </div>
        )}

        {!hasMore && (
          <p className="py-2 text-center text-xs text-[var(--color-text-secondary)]">
            {t("tools.mac_oui.history_no_more")}
          </p>
        )}
      </div>
    </div>
  );
}
