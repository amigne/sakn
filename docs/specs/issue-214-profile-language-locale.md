# Spec: Profile Language / Locale Fix (#214)

## 1. Data Schema

### Language (`language`)

**Identifiant** : code ISO 639-1 sur 2 lettres (`"en"`, `"fr"`).

**Stockage** (3 emplacements, aucun synchronisé) :

| Emplacement | Clé | Lecture | Écriture |
|---|---|---|---|
| Cookie client | `lang` | `detectLanguage()` dans `i18n.ts:11` — priorité 1 au chargement | `setLanguage()` dans `i18n.ts:49` |
| `user_preferences` DB | `key="language"` | `GET /preferences` → `preferences.language` | `PUT /preferences { language }` |
| i18next (mémoire) | `i18n.language` | `getLanguage()` dans `i18n.ts:55` | `i18n.changeLanguage()` dans `setLanguage()` |

### Locale (`locale`)

**Identifiant** : code BCP 47 (`"en-US"`, `"fr-FR"`, etc.). Contrôle le formatage des dates/nombres.

| Emplacement | Clé | Lecture | Écriture |
|---|---|---|---|
| `user_preferences` DB | `key="locale"` | `GET /preferences` → `preferences.locale` | `PUT /preferences { locale }` |
| `User.locale` (réponse auth) | — | `auth_service.py:317-325` lit `UserPreference.key="locale"` | Jamais écrit côté frontend |

**Aucun cookie, localStorage, ni usage réel côté UI pour la locale.**

## 2. Bugs identifiés (5 bugs)

### Bug 1 — `Providers.tsx:50` : Restauration de langue cassée

```typescript
// Providers.tsx:49-50 — FAUX
if (prefs?.locale) {
  import("@/i18n/i18n").then(({ setLanguage }) => setLanguage(prefs.locale!));
}
```

`prefs.locale` vaut `"en-US"` (BCP 47). `setLanguage()` valide contre `SUPPORTED_LANGUAGES = ["en", "fr"]` et rejette silencieusement. **La langue n'est jamais restaurée depuis le serveur au chargement de la page.**

**Fix** : lire `prefs.language` (pas `prefs.locale`) et appeler `setLanguage(prefs.language)`.

### Bug 2 — `ProfilePage.tsx:153-155` : Le dropdown langue persiste en DB mais ne met pas à jour l'UI

```typescript
// ProfilePage.tsx:151-158 — INCOMPLET
const saveLanguage = useCallback(
  async (lang: string) => {
    setLanguage(lang);  // state local uniquement, pas i18n !
    try {
      await savePreferences({ language: lang });  // persiste DB
      flash(t("account.language_saved"));
    } catch (_err) {}
  },
  [savePreferences],
);
```

Le `setLanguage(lang)` ici est le setter d'état local React (ligne 72), pas la fonction `setLanguage` d'i18n. La DB est mise à jour, mais le cookie, i18next, et le DOM ne le sont pas. **Changer la langue dans le dropdown du profil n'a aucun effet visible.**

**Fix** : ajouter l'appel à `import("@/i18n/i18n").setLanguage(lang)` après le `setLanguage` local.

### Bug 3 — `TopBar.tsx:48` : Le toggle langue sauve la mauvaise clé

```typescript
// TopBar.tsx:46-49 — FAUX
.savePreferences({ locale: next })  // sauve "en"/"fr" sous la clé "locale" !
```

Le toggle langue écrit le code langue (`"en"`, `"fr"`) dans la clé `locale` au lieu de `language`. **Cela pollue la préférence de locale avec un code langue.**

**Fix** : `savePreferences({ language: next })` au lieu de `{ locale: next }`.

### Bug 4 — `SessionsPage.tsx:44` : Formatage des dates sans locale

```typescript
// SessionsPage.tsx:43-48
const formatDate = (d: string) => {
  try {
    return new Date(d).toLocaleString();  // pas d'argument locale !
  } catch {
    return d;
  }
};
```

La locale stockée de l'utilisateur n'est jamais utilisée pour le formatage des dates. **La liste des sessions actives ignore le paramètre Locale.**

**Fix** : lire `preferences.locale` (ou `user.locale`) et passer à `toLocaleString(locale)`.

### Bug 5 — `ProfilePage.tsx:72-73` : État initial incorrect avant chargement des préférences

```typescript
const [language, setLanguage] = useState(preferences?.language || "en");
const [locale, setLocale] = useState(preferences?.locale || user?.locale || "en-US");
```

Au premier render, `preferences` est `null` (pas encore chargé). Le dropdown affiche toujours `"en"` / `"en-US"` initialement. Le `useEffect` ligne 96-101 corrige après chargement, mais il y a un flash visuel.

**Fix** : ce bug est cosmétique (corrigé après chargement asynchrone). On peut soit accepter le flash, soit initialiser depuis `user.locale` et le cookie. **On garde le fix simple : on accepte le flash ou on lit le cookie au démarrage.**

## 3. Source de vérité — Conflits actuels

Après un changement de langue via le **TopBar toggle** :
- Cookie `lang` : mis à jour ✅
- i18next : mis à jour ✅
- `UserPreference(locale)` : pollué avec un code langue ❌ (Bug 3)
- `UserPreference(language)` : pas touché ❌

Après un changement de langue via le **ProfilePage dropdown** :
- `UserPreference(language)` : mis à jour ✅
- Cookie `lang` : pas touché ❌ (Bug 2)
- i18next : pas touché ❌ (Bug 2)

Après un **reload de page** :
- Cookie `lang` : lu en premier → détermine la langue affichée
- `UserPreference(language)` : chargé plus tard mais jamais appliqué ❌ (Bug 1)
- Donc si l'utilisateur a changé la langue via ProfilePage, au reload elle est perdue (le cookie n'a pas été mis à jour)

## 4. État cible post-fix

1. **La source de vérité pour la langue active est le cookie `lang` + i18next**, synchronisés via `setLanguage()`.
2. **La DB (`UserPreference.key="language"`) est la source persistante**, restaurée au login/reload via `Providers.tsx`.
3. **La DB (`UserPreference.key="locale"`) stocke la locale BCP 47**, indépendante de la langue.
4. **Le dropdown Langue sur `/profile`** affiche la langue active (`getLanguage()` depuis i18n). Au changement : persiste en DB (`language`) **et** appelle `setLanguage()` pour mise à jour immédiate de l'UI.
5. **Le toggle langue dans TopBar** persiste la langue en DB avec la bonne clé (`language`).
6. **Le dropdown Locale sur `/profile`** affiche la locale stockée. Au changement : persiste en DB (`locale`).
7. **`SessionsPage`** utilise la locale de l'utilisateur pour `toLocaleString()`.
8. **`Providers.tsx`** restaure la langue depuis `prefs.language` (pas `prefs.locale`).

## 5. Non-modifications

- Pas de migration DB — `UserPreference` supporte déjà `key="language"` et `key="locale"`.
- Pas de refactoring de l'architecture i18n.
- Pas de nouvelle colonne sur `users`.
- Pas de suppression de la locale du profil (on la câble sur SessionsPage).

## 6. Plan d'implémentation

1. **`Providers.tsx:49-50`** : `setLanguage(prefs.language)` au lieu de `setLanguage(prefs.locale)`
2. **`ProfilePage.tsx:152-158`** : ajouter `setLanguage(lang)` (depuis i18n) dans `saveLanguage`
3. **`TopBar.tsx:48`** : `savePreferences({ language: next })` au lieu de `{ locale: next }`
4. **`SessionsPage.tsx:43-48`** : `toLocaleString(preferences.locale)` au lieu de `toLocaleString()`
5. **`ProfilePage.tsx:72-73`** : initialiser `language` depuis `getLanguage()` (cookie) pour éviter le flash

**Fichiers touchés** : 4 fichiers frontend (Providers.tsx, ProfilePage.tsx, TopBar.tsx, SessionsPage.tsx). **0 fichier backend.**
