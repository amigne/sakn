import enCommon from "./en/common.json";
import enTools from "./en/tools.json";
import enAuth from "./en/auth.json";
import enAdmin from "./en/admin.json";
import frCommon from "./fr/common.json";
import frTools from "./fr/tools.json";
import frAuth from "./fr/auth.json";
import frAdmin from "./fr/admin.json";

export const resources = {
  en: {
    common: enCommon,
    tools: enTools,
    auth: enAuth,
    admin: enAdmin,
  },
  fr: {
    common: frCommon,
    tools: frTools,
    auth: frAuth,
    admin: frAdmin,
  },
} as const;
