import { useTranslation } from "react-i18next";
import { Alert } from "@/components/ui";
import type { MacOuiRejected } from "@/api/tools/macOui";

interface MacOuiRejectedBannerProps {
  rejected: MacOuiRejected[];
}

export default function MacOuiRejectedBanner({ rejected }: MacOuiRejectedBannerProps) {
  const { t } = useTranslation();

  if (rejected.length === 0) return null;

  return (
    <Alert variant="warning" className="mb-3">
      <span className="font-medium">
        {t("tools.mac_oui.rejected_notice", { count: rejected.length })}
      </span>{" "}
      {rejected.map((r) => (
        <code key={r.index} className="mx-1 rounded bg-warning-200 dark:bg-warning-800 px-1 py-0.5 font-mono text-xs">
          {r.sample}
        </code>
      ))}
    </Alert>
  );
}
