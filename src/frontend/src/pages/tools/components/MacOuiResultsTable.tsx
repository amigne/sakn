import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { MacOuiResultRow } from "@/api/tools/macOui";
import { Button, Tooltip } from "@/components/ui";
import MacOuiHistoryDetails from "./MacOuiHistoryDetails";

interface MacOuiResultsTableProps {
  results: MacOuiResultRow[];
  locale: string;
}

/**
 * Render the OUI display field, replacing the `_` wildcard literal with a
 * styled span (grey + tooltip). Never uses dangerouslySetInnerHTML.
 */
function OuiDisplayCell({ display, t }: { display: string; t: (key: string) => string }) {
  return (
    <span className="font-mono text-sm">
      {display.split("").map((c, i) =>
        c === "_" ? (
          <span
            key={i}
            className="text-[var(--color-text-secondary)]"
            title={t("tools.mac_oui.tooltip_wildcard_digit")}
          >
            _
          </span>
        ) : (
          c
        ),
      )}
    </span>
  );
}

function formatDate(dateStr: string, locale: string): string {
  try {
    return new Intl.DateTimeFormat(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

export default function MacOuiResultsTable({ results, locale }: MacOuiResultsTableProps) {
  const { t } = useTranslation();
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [copiedRow, setCopiedRow] = useState<number | null>(null);

  const hasPartialByte = results.some((r) => r.result?.oui_type === "MA-M" || r.result?.oui_type === "MA-S");

  const toggleHistory = (idx: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  const copyRow = async (row: MacOuiResultRow, idx: number) => {
    if (!row.result) return;
    const text = `${row.result.organization}\t${row.result.address}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedRow(idx);
      setTimeout(() => setCopiedRow(null), 2000);
    } catch {
      // Clipboard unavailable — silently ignore.
    }
  };

  const copyAll = async () => {
    const header = ["OUI", "Vendor", "Type", "First seen", "Last seen", "Address"].join("\t");
    const lines = results.map((r) => {
      const oui = r.oui_display;
      const vendor = r.result?.organization ?? t("tools.mac_oui.unknown_vendor");
      const type = r.result?.oui_type ?? "—";
      const first = r.result ? formatDate(r.result.first_seen, locale) : "—";
      const last = r.result ? formatDate(r.result.last_seen, locale) : "—";
      const addr = r.result?.address ?? "—";
      return [oui, vendor, type, first, last, addr].join("\t");
    });
    try {
      await navigator.clipboard.writeText(`${header}\n${lines.join("\n")}`);
    } catch {
      // Clipboard unavailable — silently ignore.
    }
  };

  if (results.length === 0) return null;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">
          {t("common.results")} ({results.length})
        </h3>
        <Button variant="secondary" size="sm" onClick={copyAll} aria-label={t("tools.mac_oui.copy_global")}>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          {t("tools.mac_oui.copy_global")}
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                {t("tools.mac_oui.result_oui")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                {t("tools.mac_oui.result_vendor")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                {t("tools.mac_oui.result_type")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                {t("tools.mac_oui.result_first_seen")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                {t("tools.mac_oui.result_last_seen")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                {t("tools.mac_oui.result_address")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide"
              >
                <span className="sr-only">{t("common.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {results.map((row, idx) => {
              const isAmbiguous = row.ambiguous_extends_ma_m || row.ambiguous_extends_ma_s;
              const hasHistory = row.history.length > 0;

              return (
                <tr
                  key={row.input}
                  className={`border-b border-[var(--color-border)] ${
                    isAmbiguous ? "bg-[var(--color-warning-soft)]" : ""
                  }`}
                >
                  <td className="px-3 py-2">
                    {isAmbiguous && (
                      <Tooltip content={t("tools.mac_oui.ambiguous_partial_oui")}>
                        <span
                          role="img"
                          aria-label={t("tools.mac_oui.ambiguous_partial_oui")}
                          className="me-1 cursor-help text-warning-600"
                        >
                          &#9888;
                        </span>
                      </Tooltip>
                    )}
                    <OuiDisplayCell display={row.oui_display} t={t} />
                  </td>
                  <td className="px-3 py-2 text-[var(--color-text)]">
                    {row.result?.organization ?? (
                      <span className="text-[var(--color-text-secondary)]">{t("tools.mac_oui.unknown_vendor")}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[var(--color-text)] font-mono text-xs">
                    {row.result?.oui_type ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-[var(--color-text-secondary)] font-mono text-xs whitespace-nowrap">
                    {row.result ? formatDate(row.result.first_seen, locale) : "—"}
                  </td>
                  <td className="px-3 py-2 text-[var(--color-text-secondary)] font-mono text-xs whitespace-nowrap">
                    {row.result ? formatDate(row.result.last_seen, locale) : "—"}
                  </td>
                  <td
                    className="px-3 py-2 text-[var(--color-text-secondary)] max-w-40 truncate"
                    title={row.result?.address ?? undefined}
                  >
                    {row.result?.address ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {row.result && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyRow(row, idx)}
                          aria-label={t("tools.mac_oui.copy_row")}
                        >
                          {copiedRow === idx ? (
                            <span className="text-xs text-success-600">{t("tools.mac_oui.copied")}</span>
                          ) : (
                            <svg
                              className="h-3.5 w-3.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                              />
                            </svg>
                          )}
                        </Button>
                      )}
                      {hasHistory && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleHistory(idx)}
                          aria-expanded={expandedRows.has(idx)}
                          aria-label={t("tools.mac_oui.history_button")}
                        >
                          <svg className={`h-3.5 w-3.5 transition-transform ${expandedRows.has(idx) ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                          </svg>
                          {t("tools.mac_oui.history_button")}
                        </Button>
                      )}
                    </div>
                    {hasHistory && expandedRows.has(idx) && (
                      <MacOuiHistoryDetails history={row.history} />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hasPartialByte && (
        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
          {t("tools.mac_oui.legend_partial_byte")}
        </p>
      )}
    </div>
  );
}
