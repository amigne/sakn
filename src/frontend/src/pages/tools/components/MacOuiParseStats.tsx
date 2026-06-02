import { useTranslation } from "react-i18next";
import type { MacOuiParseStats as MacOuiParseStatsType } from "@/api/tools/macOui";

interface MacOuiParseStatsProps {
  stats: MacOuiParseStatsType;
}

export default function MacOuiParseStats({ stats }: MacOuiParseStatsProps) {
  const { t } = useTranslation();

  return (
    <p className="mb-3 text-sm text-[var(--color-text-secondary)]">
      {t("tools.mac_oui.parse_stats", {
        found: stats.total_inputs,
        unique: stats.unique,
      })}
    </p>
  );
}
