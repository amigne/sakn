# i18n Namespace Separation

> **Version:** 1.0 — New document
> **Status:** Draft
> **Date:** 2026-05-26
> **Issue:** #3

## 1. Current State

All 484 translation keys live in a single flat JSON file per language (`en.json`, `fr.json`), imported directly in `resources.ts`:

```
src/i18n/
  i18n.ts       — i18next init, language detection, dir
  resources.ts  — imports en.json + fr.json as single "translation" NS
  en.json       — 484 keys, flat
  fr.json       — 484 keys, flat
```

All components use `useTranslation()` with the default namespace, so keys are referenced as `t("tools.ping.name")`.

## 2. Target Namespaces

| Namespace | Key count | Contains | defaultNS? |
|-----------|-----------|----------|------------|
| `common` | ~78 | `common.*`, `cookies.*`, `privacy.*`, `notools.*` | Yes |
| `auth` | ~81 | `auth.*`, `account.*` | No |
| `tools` | ~142 | `tools.*` | No |
| `admin` | ~149 | `admin.*` | No |
| `errors` | ~34 | `errors.*` | No |
| `notices` | ~2 | `notices.*` | No |
| `sessions` | ~2 | `sessions.*` | No |

Total: ~488 keys (minor variance from source).

## 3. Migration Strategy

### 3.1 Pilot: `errors` namespace (this PR)

The `errors` namespace is the smallest, most self-contained, and has no overlap with other namespaces. It serves as proof of concept for the multi-namespace setup.

**Steps:**

1. Create `src/i18n/errors/en.json` and `src/i18n/errors/fr.json` with only the `errors.*` keys (key names without the `errors.` prefix — e.g., `errors.invalid_email` becomes `invalid_email`).

2. Update `resources.ts` to load namespaces:
   ```ts
   import errorsEn from "./errors/en.json";
   import errorsFr from "./errors/fr.json";
   // ...other namespaces loaded as empty stubs
   
   const resources = {
     en: { common: commonEn, errors: errorsEn, ... },
     fr: { common: commonFr, errors: errorsFr, ... },
   };
   ```

3. Configure `ns`, `defaultNS` in `i18n.ts`:
   ```ts
   defaultNS: "common",
   ns: ["common", "errors", "auth", "tools", "admin", "notices", "sessions"],
   ```

4. Update all `t("errors.xxx")` calls to `t("errors:xxx")` (colon separator).

5. For the `common` namespace (defaultNS), no prefix needed: `t("loading")` instead of `t("common.loading")`. But for other namespaces: `t("errors:invalid_email")` instead of `t("errors.invalid_email")`.

### 3.2 Follow-up PRs (one per namespace)

- PR 2: Migrate `notices` (2 keys)
- PR 3: Migrate `sessions` (2 keys)
- PR 4: Migrate `auth` + `account` (81 keys)
- PR 5: Migrate `tools` (142 keys)
- PR 6: Migrate `admin` (149 keys)
- PR 7: Migrate `common` (78 keys) — last, since it's the defaultNS

## 4. Component Impact

When using `useTranslation()` with defaultNS=`common`:
- `t("loading")` → resolves from `common` namespace
- `t("errors:invalid_email")` → resolves from `errors` namespace
- `t("auth:sign_in")` → resolves from `auth` namespace

For components that use mostly one namespace, use `useTranslation("errors")`:
- `t("errors:invalid_email")` becomes `t("invalid_email")`

## 5. Acceptance Criteria

- [ ] `npm run dev` — all pages render without raw key strings
- [ ] Playwright E2E suite passes (all screens display correct labels)
- [ ] `useTranslation("errors")` resolves keys correctly
- [ ] `t("errors:invalid_email")` resolves when using default namespace
- [ ] Fallback to `common` namespace works for keys not found in non-default NS
- [ ] TypeScript compiles without errors
- [ ] Common keys (`common.loading`) still work as `t("loading")`
