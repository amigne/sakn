import { useState } from "react";
import PageLayout from "@/components/layout/PageLayout";
import { Select, RadioButton, Button } from "@/components/ui";
import { useThemeStore } from "@/stores/themeStore";
import { useAuthStore } from "@/stores/authStore";
import type { ThemeMode } from "@/types/user";

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const { mode, setMode } = useThemeStore();
  const [language, setLanguage] = useState("en");
  const [locale, setLocale] = useState(user?.locale || "en-US");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <PageLayout>
      <div className="max-w-lg">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">Preferences</h1>

        <div className="card p-4 space-y-4">
          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Language</span>
              <Select
                options={[{ value: "en", label: "English" }, { value: "fr", label: "Français" }]}
                value={language}
                onChange={setLanguage}
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
                  onChange={() => setMode(m)}
                  label={m.charAt(0).toUpperCase() + m.slice(1)}
                />
              ))}
            </div>
          </div>

          <div>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">Locale</span>
              <Select
                options={[
                  { value: "en-US", label: "English (US)" },
                  { value: "en-GB", label: "English (UK)" },
                  { value: "fr-FR", label: "Français (France)" },
                  { value: "fr-CA", label: "Français (Canada)" },
                ]}
                value={locale}
                onChange={setLocale}
              />
            </label>
          </div>

          <Button onClick={handleSave}>
            {saved ? "Saved" : "Save Preferences"}
          </Button>
        </div>
      </div>
    </PageLayout>
  );
}
