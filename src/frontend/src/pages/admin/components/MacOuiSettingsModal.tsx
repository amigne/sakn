import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getModuleSettings, updateModuleSettings } from "@/api/admin/moduleStatus";
import { Button, Modal, Spinner, TextInput } from "@/components/ui";

interface SettingsState {
  MAC_OUI_FRONTEND_INPUT_MAX_CHARS: string;
  MAC_OUI_BACKEND_BATCH_MAX_SIZE: string;
  MAC_OUI_HISTORY_PAGE_SIZE: string;
  OUI_SYNC_HOUR: string;
}

const DEFAULTS: SettingsState = {
  MAC_OUI_FRONTEND_INPUT_MAX_CHARS: "50000",
  MAC_OUI_BACKEND_BATCH_MAX_SIZE: "2000",
  MAC_OUI_HISTORY_PAGE_SIZE: "10",
  OUI_SYNC_HOUR: "3",
};

const SETTING_DEFS = [
  {
    key: "MAC_OUI_FRONTEND_INPUT_MAX_CHARS" as const,
    labelKey: "admin.mac_oui_settings.frontend_input_max_chars",
    min: 1000,
    max: 200000,
  },
  {
    key: "MAC_OUI_BACKEND_BATCH_MAX_SIZE" as const,
    labelKey: "admin.mac_oui_settings.backend_batch_max_size",
    min: 100,
    max: 10000,
  },
  {
    key: "MAC_OUI_HISTORY_PAGE_SIZE" as const,
    labelKey: "admin.mac_oui_settings.history_page_size",
    min: 5,
    max: 50,
  },
  {
    key: "OUI_SYNC_HOUR" as const,
    labelKey: "admin.mac_oui_settings.sync_hour",
    min: 0,
    max: 23,
  },
];

interface MacOuiSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function MacOuiSettingsModal({ open, onClose }: MacOuiSettingsModalProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [values, setValues] = useState<SettingsState>({ ...DEFAULTS });

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getModuleSettings("mac_oui");
      const remote = data.settings ?? {};
      setValues({
        MAC_OUI_FRONTEND_INPUT_MAX_CHARS:
          remote.MAC_OUI_FRONTEND_INPUT_MAX_CHARS ?? DEFAULTS.MAC_OUI_FRONTEND_INPUT_MAX_CHARS,
        MAC_OUI_BACKEND_BATCH_MAX_SIZE:
          remote.MAC_OUI_BACKEND_BATCH_MAX_SIZE ?? DEFAULTS.MAC_OUI_BACKEND_BATCH_MAX_SIZE,
        MAC_OUI_HISTORY_PAGE_SIZE: remote.MAC_OUI_HISTORY_PAGE_SIZE ?? DEFAULTS.MAC_OUI_HISTORY_PAGE_SIZE,
        OUI_SYNC_HOUR: remote.OUI_SYNC_HOUR ?? DEFAULTS.OUI_SYNC_HOUR,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_load_settings"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (open) {
      setSaved(false);
      fetchSettings();
    }
  }, [open, fetchSettings]);

  const handleChange = (key: keyof SettingsState, raw: string) => {
    // Allow only digits
    const cleaned = raw.replace(/\D/g, "");
    setValues((prev) => ({ ...prev, [key]: cleaned }));
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateModuleSettings("mac_oui", {
        MAC_OUI_FRONTEND_INPUT_MAX_CHARS: values.MAC_OUI_FRONTEND_INPUT_MAX_CHARS,
        MAC_OUI_BACKEND_BATCH_MAX_SIZE: values.MAC_OUI_BACKEND_BATCH_MAX_SIZE,
        MAC_OUI_HISTORY_PAGE_SIZE: values.MAC_OUI_HISTORY_PAGE_SIZE,
        OUI_SYNC_HOUR: values.OUI_SYNC_HOUR,
      });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_save_settings"));
    } finally {
      setSaving(false);
    }
  }, [values, t]);

  return (
    <Modal open={open} onClose={onClose} title={t("admin.mac_oui_settings.title")}>
      <div className="space-y-4">
        {loading ? (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        ) : (
          <>
            {error && (
              <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">
                {error}
              </div>
            )}
            {saved && (
              <div className="p-3 rounded bg-green-50 dark:bg-green-950 text-sm text-green-700 dark:text-green-300">
                {t("admin.mac_oui_settings.saved")}
              </div>
            )}

            {SETTING_DEFS.map((def) => (
              <div key={def.key} className="space-y-1">
                <label
                  htmlFor={`setting-${def.key}`}
                  className="text-xs font-medium text-[var(--color-text-secondary)]"
                >
                  {t(def.labelKey)}
                </label>
                <TextInput
                  id={`setting-${def.key}`}
                  type="number"
                  min={def.min}
                  max={def.max}
                  value={values[def.key]}
                  onChange={(e) => handleChange(def.key, e.target.value)}
                />
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {def.min} – {def.max}
                </p>
              </div>
            ))}

            <div className="flex justify-end pt-2">
              <Button size="sm" variant="primary" loading={saving} onClick={handleSave}>
                {t("admin.mac_oui_settings.save")}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
