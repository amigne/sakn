import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { resources } from "./resources";

const SUPPORTED_LANGUAGES = ["en", "fr"] as const;
const DEFAULT_LANGUAGE = "en";

function detectLanguage(): string {
  // 1. Check for stored preference (cookie)
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)lang=([^;]*)/);
    if (match?.[1] && SUPPORTED_LANGUAGES.includes(match[1] as (typeof SUPPORTED_LANGUAGES)[number])) {
      return match[1];
    }
  }
  // 2. Browser preference
  if (typeof navigator !== "undefined") {
    const browserLang = navigator.language?.slice(0, 2);
    if (browserLang && SUPPORTED_LANGUAGES.includes(browserLang as (typeof SUPPORTED_LANGUAGES)[number])) {
      return browserLang;
    }
  }
  return DEFAULT_LANGUAGE;
}

i18n.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: "common",
  ns: ["common", "errors"],
  interpolation: {
    escapeValue: false,
  },
  returnNull: false,
  returnEmptyString: false,
});

function getDirForLang(_lang: string): "ltr" | "rtl" {
  // RTL languages would return "rtl" here (e.g., "ar", "he", "fa")
  return "ltr";
}

export function setLanguage(lang: string): void {
  if (!SUPPORTED_LANGUAGES.includes(lang as (typeof SUPPORTED_LANGUAGES)[number])) return;
  i18n.changeLanguage(lang);
  const secureFlag = typeof window !== "undefined" && window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `lang=${lang};path=/;max-age=${60 * 60 * 24 * 365};SameSite=Lax${secureFlag}`;
  document.documentElement.lang = lang;
  document.documentElement.dir = getDirForLang(lang);
}

export function getLanguage(): string {
  return i18n.language || DEFAULT_LANGUAGE;
}

export default i18n;
