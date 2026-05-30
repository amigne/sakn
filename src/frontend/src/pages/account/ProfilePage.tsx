import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";
import { RadioButton, Select, TextInput } from "@/components/ui";
import { getLanguage, setLanguage as setI18nLanguage } from "@/i18n/i18n";
import { ApiError } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import { useThemeStore } from "@/stores/themeStore";
import type { ThemeMode } from "@/types/user";

const LOCALE_CODES = [
  "af-ZA",
  "ar-SA",
  "bg-BG",
  "ca-ES",
  "cs-CZ",
  "da-DK",
  "de-DE",
  "el-GR",
  "en-AU",
  "en-CA",
  "en-GB",
  "en-IE",
  "en-IN",
  "en-NZ",
  "en-US",
  "es-ES",
  "es-MX",
  "fi-FI",
  "fr-BE",
  "fr-CA",
  "fr-CH",
  "fr-FR",
  "he-IL",
  "hi-IN",
  "hr-HR",
  "hu-HU",
  "id-ID",
  "it-IT",
  "ja-JP",
  "ko-KR",
  "nl-NL",
  "no-NO",
  "pl-PL",
  "pt-BR",
  "pt-PT",
  "ro-RO",
  "ru-RU",
  "sk-SK",
  "sv-SE",
  "th-TH",
  "tr-TR",
  "uk-UA",
  "vi-VN",
  "zh-CN",
  "zh-TW",
];

const LANGUAGE_TO_DEFAULT_LOCALE: Record<string, string> = {
  en: "en-US",
  fr: "fr-FR",
};

/** Extract the two-letter root from a potentially full locale code (e.g. "fr-CH" → "fr"). */
function getLanguageRoot(): string {
  return getLanguage().split("-")[0]!;
}

function buildLocaleLabels(displayLang: string) {
  const langNames = new Intl.DisplayNames([displayLang], { type: "language" });
  const regionNames = new Intl.DisplayNames([displayLang], { type: "region" });
  return LOCALE_CODES.map((code) => {
    const [lang, region] = code.split("-");
    const langName = langNames.of(lang!) ?? lang!;
    const regionName = region ? (regionNames.of(region) ?? region) : null;
    return {
      value: code,
      label: regionName ? `${langName} (${regionName})` : langName,
    };
  });
}

export default function ProfilePage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const preferences = useAuthStore((s) => s.preferences);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const savePreferences = useAuthStore((s) => s.savePreferences);
  const loadPreferences = useAuthStore((s) => s.loadPreferences);
  const { mode, setMode } = useThemeStore();

  const initialFirst = user?.first_name ?? "";
  const initialLast = user?.last_name ?? "";

  const [firstName, setFirstName] = useState(initialFirst);
  const [lastName, setLastName] = useState(initialLast);
  const [language, setLanguage] = useState(getLanguage());
  const [locale, setLocale] = useState(
    preferences?.locale || LANGUAGE_TO_DEFAULT_LOCALE[getLanguageRoot()] || user?.locale || "en-US",
  );
  const allLocales = useMemo(() => buildLocaleLabels(language), [language]);
  const [saved, setSaved] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep track of last valid values for rollback
  const lastGoodFirst = useRef(initialFirst);
  const lastGoodLast = useRef(initialLast);

  // Update local state when user or preferences change from store
  useEffect(() => {
    if (user) {
      setFirstName(user.first_name ?? "");
      setLastName(user.last_name ?? "");
      lastGoodFirst.current = user.first_name ?? "";
      lastGoodLast.current = user.last_name ?? "";
    }
  }, [user?.first_name, user?.last_name]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  useEffect(() => {
    if (preferences) {
      setLanguage(preferences.language || getLanguage());
      setLocale(preferences.locale || LANGUAGE_TO_DEFAULT_LOCALE[getLanguageRoot()] || user?.locale || "en-US");
    }
  }, [preferences, user?.locale]);

  const flash = (label: string) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaved(label);
    saveTimer.current = setTimeout(() => setSaved(null), 1500);
  };

  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, []);

  const trim = (s: string) => s.trim();

  const saveNames = useCallback(async () => {
    const trimmedFirst = trim(firstName);
    const trimmedLast = trim(lastName);

    // Sync display with trimmed values
    setFirstName(trimmedFirst);
    setLastName(trimmedLast);

    if (!trimmedFirst || !trimmedLast) {
      // Revert to last good values
      setFirstName(lastGoodFirst.current);
      setLastName(lastGoodLast.current);
      setNameError(t("account.name_empty_error"));
      return;
    }

    setNameError(null);
    try {
      await updateProfile(trimmedFirst, trimmedLast);
      lastGoodFirst.current = trimmedFirst;
      lastGoodLast.current = trimmedLast;
      flash(t("account.name_saved"));
    } catch (err) {
      // Revert to last good values on API error
      setFirstName(lastGoodFirst.current);
      setLastName(lastGoodLast.current);
      if (err instanceof ApiError) {
        setNameError(err.message);
      } else {
        setNameError(t("account.name_save_failed"));
      }
    }
  }, [firstName, lastName, updateProfile]);

  const saveLanguage = useCallback(
    async (lang: string) => {
      setLanguage(lang);
      setI18nLanguage(lang);
      try {
        await savePreferences({ language: lang });
        flash(t("account.language_saved"));
      } catch (_err) {}
    },
    [savePreferences],
  );

  const saveLocale = useCallback(
    async (loc: string) => {
      setLocale(loc);
      try {
        await savePreferences({ locale: loc });
        flash(t("account.locale_saved"));
      } catch (_err) {}
    },
    [savePreferences],
  );

  const handleThemeChange = useCallback(
    async (m: ThemeMode) => {
      setMode(m);
      try {
        await savePreferences({ theme: m });
        flash(t("account.theme_saved"));
      } catch (_err) {}
    },
    [setMode, savePreferences],
  );

  return (
    <PageLayout>
      <div className="max-w-lg">
        <div className="flex items-center gap-3 mb-4">
          <h1 className="text-lg font-semibold text-[var(--color-text)]">{t("account.profile")}</h1>
          {saved && <span className="text-xs text-green-600 dark:text-green-400 animate-pulse">{saved}</span>}
        </div>

        <div className="card p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.first_name")}</span>
              <TextInput
                type="text"
                value={firstName}
                onChange={(e) => {
                  setFirstName(e.target.value);
                  setNameError(null);
                }}
                onBlur={() => saveNames()}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.last_name")}</span>
              <TextInput
                type="text"
                value={lastName}
                onChange={(e) => {
                  setLastName(e.target.value);
                  setNameError(null);
                }}
                onBlur={() => saveNames()}
              />
            </label>
          </div>
          {nameError && <p className="text-xs text-red-600 -mt-2">{nameError}</p>}

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.email")}</span>
              <TextInput type="email" value={user?.email || ""} disabled />
            </label>
          </div>

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">{t("account.language")}</span>
              <Select
                options={[
                  { value: "en", label: t("account.locale_en") },
                  { value: "fr", label: t("account.locale_fr") },
                ]}
                value={language}
                onChange={saveLanguage}
                ariaLabel={t("account.language")}
              />
            </label>
          </div>

          <div>
            <span className="text-sm font-medium text-[var(--color-text)]">{t("account.theme")}</span>
            <div className="mt-2 space-y-2">
              {(["light", "dark", "system"] as ThemeMode[]).map((m) => (
                <RadioButton
                  key={m}
                  name="theme"
                  checked={mode === m}
                  onChange={() => handleThemeChange(m)}
                  label={t(`account.theme_${m}`)}
                />
              ))}
            </div>
          </div>

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">{t("account.locale")}</span>
              <Select options={allLocales} value={locale} onChange={saveLocale} ariaLabel={t("account.locale")} />
            </label>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
