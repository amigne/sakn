import { useState, useRef, useCallback, useEffect } from "react";
import PageLayout from "@/components/layout/PageLayout";
import { Select, RadioButton, TextInput } from "@/components/ui";
import { useThemeStore } from "@/stores/themeStore";
import { useAuthStore } from "@/stores/authStore";
import type { ThemeMode } from "@/types/user";
import { ApiError } from "@/services/api";

const ALL_LOCALES: { value: string; label: string }[] = [
  { value: "af-ZA", label: "Afrikaans (South Africa)" },
  { value: "ar-SA", label: "Arabic (Saudi Arabia)" },
  { value: "bg-BG", label: "Bulgarian (Bulgaria)" },
  { value: "ca-ES", label: "Catalan (Spain)" },
  { value: "cs-CZ", label: "Czech (Czechia)" },
  { value: "da-DK", label: "Danish (Denmark)" },
  { value: "de-DE", label: "German (Germany)" },
  { value: "el-GR", label: "Greek (Greece)" },
  { value: "en-AU", label: "English (Australia)" },
  { value: "en-CA", label: "English (Canada)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "en-IE", label: "English (Ireland)" },
  { value: "en-IN", label: "English (India)" },
  { value: "en-NZ", label: "English (New Zealand)" },
  { value: "en-US", label: "English (US)" },
  { value: "es-ES", label: "Spanish (Spain)" },
  { value: "es-MX", label: "Spanish (Mexico)" },
  { value: "fi-FI", label: "Finnish (Finland)" },
  { value: "fr-BE", label: "French (Belgium)" },
  { value: "fr-CA", label: "French (Canada)" },
  { value: "fr-CH", label: "French (Switzerland)" },
  { value: "fr-FR", label: "French (France)" },
  { value: "he-IL", label: "Hebrew (Israel)" },
  { value: "hi-IN", label: "Hindi (India)" },
  { value: "hr-HR", label: "Croatian (Croatia)" },
  { value: "hu-HU", label: "Hungarian (Hungary)" },
  { value: "id-ID", label: "Indonesian (Indonesia)" },
  { value: "it-IT", label: "Italian (Italy)" },
  { value: "ja-JP", label: "Japanese (Japan)" },
  { value: "ko-KR", label: "Korean (South Korea)" },
  { value: "nl-NL", label: "Dutch (Netherlands)" },
  { value: "no-NO", label: "Norwegian (Norway)" },
  { value: "pl-PL", label: "Polish (Poland)" },
  { value: "pt-BR", label: "Portuguese (Brazil)" },
  { value: "pt-PT", label: "Portuguese (Portugal)" },
  { value: "ro-RO", label: "Romanian (Romania)" },
  { value: "ru-RU", label: "Russian (Russia)" },
  { value: "sk-SK", label: "Slovak (Slovakia)" },
  { value: "sv-SE", label: "Swedish (Sweden)" },
  { value: "th-TH", label: "Thai (Thailand)" },
  { value: "tr-TR", label: "Turkish (Turkey)" },
  { value: "uk-UA", label: "Ukrainian (Ukraine)" },
  { value: "vi-VN", label: "Vietnamese (Vietnam)" },
  { value: "zh-CN", label: "Chinese (Simplified)" },
  { value: "zh-TW", label: "Chinese (Traditional)" },
];

export default function ProfilePage() {
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
  const [language, setLanguage] = useState(preferences?.language || "en");
  const [locale, setLocale] = useState(preferences?.locale || user?.locale || "en-US");
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
      setLanguage(preferences.language || "en");
      setLocale(preferences.locale || user?.locale || "en-US");
    }
  }, [preferences, user?.locale]);

  const flash = (label: string) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaved(label);
    saveTimer.current = setTimeout(() => setSaved(null), 1500);
  };

  useEffect(() => {
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
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
      setNameError("First name and last name cannot be empty.");
      return;
    }

    setNameError(null);
    try {
      await updateProfile(trimmedFirst, trimmedLast);
      lastGoodFirst.current = trimmedFirst;
      lastGoodLast.current = trimmedLast;
      flash("Name saved");
    } catch (err) {
      // Revert to last good values on API error
      setFirstName(lastGoodFirst.current);
      setLastName(lastGoodLast.current);
      if (err instanceof ApiError) {
        setNameError(err.message);
      } else {
        setNameError("Failed to save names.");
      }
    }
  }, [firstName, lastName, updateProfile]);

  const saveLanguage = useCallback(async (lang: string) => {
    setLanguage(lang);
    try {
      await savePreferences({ language: lang });
      flash("Language saved");
    } catch (_err) {}
  }, [savePreferences]);

  const saveLocale = useCallback(async (loc: string) => {
    setLocale(loc);
    try {
      await savePreferences({ locale: loc });
      flash("Locale saved");
    } catch (_err) {}
  }, [savePreferences]);

  const handleThemeChange = useCallback(async (m: ThemeMode) => {
    setMode(m);
    try {
      await savePreferences({ theme: m });
      flash("Theme saved");
    } catch (_err) {}
  }, [setMode, savePreferences]);

  return (
    <PageLayout>
      <div className="max-w-lg">
        <div className="flex items-center gap-3 mb-4">
          <h1 className="text-lg font-semibold text-[var(--color-text)]">Profile</h1>
          {saved && (
            <span className="text-xs text-green-600 dark:text-green-400 animate-pulse">{saved}</span>
          )}
        </div>

        <div className="card p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">First Name</span>
              <TextInput type="text" value={firstName} onChange={(e) => { setFirstName(e.target.value); setNameError(null); }} onBlur={() => saveNames()} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Last Name</span>
              <TextInput type="text" value={lastName} onChange={(e) => { setLastName(e.target.value); setNameError(null); }} onBlur={() => saveNames()} />
            </label>
          </div>
          {nameError && <p className="text-xs text-red-600 -mt-2">{nameError}</p>}

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Email</span>
              <TextInput type="email" value={user?.email || ""} disabled />
            </label>
          </div>

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Language</span>
              <Select
                options={[
                  { value: "en", label: "English" },
                  { value: "fr", label: "Français" },
                ]}
                value={language}
                onChange={saveLanguage}
              />
            </label>
          </div>

          <div>
            <span className="text-sm font-medium text-[var(--color-text)]">Theme</span>
            <div className="mt-2 space-y-2">
              {(["light", "dark", "system"] as ThemeMode[]).map((m) => (
                <RadioButton
                  key={m}
                  name="theme"
                  checked={mode === m}
                  onChange={() => handleThemeChange(m)}
                  label={m.charAt(0).toUpperCase() + m.slice(1)}
                />
              ))}
            </div>
          </div>

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Locale</span>
              <Select options={ALL_LOCALES} value={locale} onChange={saveLocale} />
            </label>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
