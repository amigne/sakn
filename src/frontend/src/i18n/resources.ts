import commonEn from "./en.json";
import errorsEn from "./errors/en.json";
import errorsFr from "./errors/fr.json";
import commonFr from "./fr.json";

export const resources = {
  en: {
    common: commonEn,
    errors: errorsEn,
  },
  fr: {
    common: commonFr,
    errors: errorsFr,
  },
} as const;
