# Frontend Specification — SAKN MVP

> **Version:** 4.0 — Added MAC OUI, WHOIS, Secret Generator pages
> **Status:** Draft
> **Date:** 2026-05-21

Client-side architecture. Load with `spec-common.md` and `spec-api-contract.md`. For tool pages, also load the relevant tool spec (`spec-tools-live.md` or `spec-tools-instant.md`).

---

## 1. Component Architecture

```
src/
  frontend/
    package.json
    vite.config.ts
    tsconfig.json
    tailwind.config.ts
    index.html
    Dockerfile                # Nginx + static files (production)

    src/
      App.tsx                 # Root: providers, router
      Router.tsx              # Route definitions
      Providers.tsx           # QueryClientProvider, ThemeProvider, I18nProvider

      pages/
        tools/
          PingPage.tsx
          TraceroutePage.tsx
          DnsLookupPage.tsx
          SslViewerPage.tsx
          MacOuiLookupPage.tsx
          WhoisLookupPage.tsx
          SecretGeneratorPage.tsx
        auth/
          LoginPage.tsx
          RegisterPage.tsx
          VerifyEmailPage.tsx
          ResetPasswordPage.tsx
        admin/
          AdminUsersPage.tsx
          AdminUserDetailPage.tsx
          AdminAccessPage.tsx
          AdminRateLimitsPage.tsx
          AdminModulesPage.tsx
          AdminSettingsPage.tsx
          AdminLogsPage.tsx
        account/
          ProfilePage.tsx
          SessionsPage.tsx

      components/
        ui/                   # Atomic: Button, Input, Select, Table, etc.
        layout/               # Header, Sidebar, Footer, PageLayout
        tool/                 # ToolInputForm, ToolResultViewer, ToolParameterField
        auth/                 # LoginForm, RegisterForm, PasswordStrengthIndicator
        admin/                # UserTable, LogTable, RateLimitEditor

      hooks/
        useToolExecution.ts   # Mutation hook (instant tools)
        useWebSocket.ts       # WebSocket hook (continuous tools)
        useAuth.ts            # Login, logout, current user

        useSession.ts         # Session management
      // Note: Preferences are managed via authStore (Zustand) and themeStore, not a dedicated hook.

      services/
        api.ts                # Base API client (fetch wrapper with CSRF)
        auth.ts               # Auth API calls

        admin.ts              # Admin API calls
        preferences.ts        # Preferences API calls
      // Note: Tool API calls use useWebSocket and useToolExecution hooks directly rather than a separate service layer.

      stores/
        authStore.ts          # Auth state (current user)
        themeStore.ts         # Theme state (light/dark/system)
        toolStore.ts          # Active tool config, table/text view toggle

      i18n/
        resources.ts          # Import all translation namespaces
        en/
          common.json
          tools.json
          auth.json
          admin.json
        fr/
          common.json
          tools.json
          auth.json
          admin.json

      types/
        api.ts                # API response/request types
        tool.ts               # Tool definition and result types
        user.ts               # User, session types
        admin.ts              # Admin types
```

---

## 2. State Management

| Data | Store | Persistence |
|---|---|---|
| Current user / auth status | Zustand `authStore` | In-memory (session cookie is httpOnly) |
| Theme preference | Zustand `themeStore` | localStorage (visitor) + API (auth'd) |
| Language & locale | Zustand + i18n | localStorage (visitor) + API (auth'd) |
| Table/text view toggle | Zustand `toolStore` | localStorage (per-tool, per-user) |
| Server data (tool results, users, logs) | TanStack Query cache | In-memory with TTL |
| Form state | React Hook Form local state | Not persisted |

**Why Zustand**: minimal boilerplate, TypeScript-native, selector-based subscriptions (no unnecessary re-renders unlike React Context).

---

## 3. WebSocket Client Behavior

For continuous tools (Ping, Traceroute). See `spec-tools-live.md` for the server-side protocol.

1. **Start**: open WebSocket to `wss://<host>/api/v1/tools/{tool_name}/stream` (authenticated via session cookie), send `{"type": "start", "params": {...}}`. Execute button becomes Stop.
2. **Stream**: on each `result` message, append to display (new row in table or line in text view).
3. **Notice**: on `notice` message, display as non-blocking banner or inline info.
4. **Complete**: on `complete` message, render final summary, close WebSocket, re-enable Execute button.
5. **Stop**: on user click, send `{"type": "cancel"}`, wait for `complete`, close WebSocket.
6. **Navigate away**: close WebSocket (server treats disconnect as implicit cancel).
7. **Error**: before any `result` → display in output panel (tool didn't start). After some `result` → display banner above partial results.

---

## 4. HTTP Tool Execution

For instant tools (DNS Lookup, TLS/SSL Viewer, MAC OUI Lookup, WHOIS Lookup). See `spec-tools-instant.md` for server-side details.

1. Disable Execute button.
2. POST to `/api/v1/tools/{tool_name}/execute` with `{"params": {...}}`.
3. On 200: render result data.
4. On error (4xx/5xx): render error message with i18n translation of `message_key`.
5. Re-enable Execute button.

### 4.1 MAC OUI Lookup — Textarea Input

The MAC OUI Lookup page uses a `<textarea>` instead of a single-line `<input>`. The user can paste arbitrary text (ARP tables, CAM tables, etc.). The frontend sends the raw text as a single `text` parameter. The backend handles extraction and deduplication.

### 4.2 Secret Generator — Frontend-Only Tool

No API call is made. The tool is identified by `backend: false` in the `/tools` response. All logic runs client-side.

The tool has 3 generation modes, selected via a tab bar or radio group:

#### Mode 1: Password

1. User configures length (slider, 8–128) and character sets (4 checkboxes: uppercase, lowercase, digits, symbols). At least one charset required.
2. On "Generate" click: `crypto.getRandomValues()` fills a `Uint8Array`, mapped to selected character sets via rejection sampling (modulo bias-free uniform distribution).
3. Entropy: `bits = length * log2(charset_size)`.

#### Mode 2: Token (URL-safe)

1. User configures length in characters (slider or numeric input, 16–256, default 43).
2. Entropy per character: 6 bits (base64url charset = 64 symbols: A-Z, a-z, 0-9, `-`, `_`).
3. Display shows: `"N caractères (X bits)"` where X = N * 6.
4. On "Generate" click: `crypto.getRandomValues()` fills a `Uint8Array` of `ceil(length * 6 / 8)` bytes, encoded to base64url (RFC 4648 §5: `-` instead of `+`, `_` instead of `/`, no `=` padding). Output length may be ±1 char from requested; actual length and bits are shown.
5. Equivalent to Python `secrets.token_urlsafe()` (for 43 chars: `secrets.token_urlsafe(32)`).

#### Mode 3: Hex

1. User configures length in characters (slider or numeric input, 16–512, default 64).
2. Entropy per character: 4 bits (hex charset = 16 symbols: 0-9, a-f).
3. Display shows: `"N caractères (X bits)"` where X = N * 4.
4. On "Generate" click: `crypto.getRandomValues()` fills a `Uint8Array` of `ceil(length / 2)` bytes, encoded as lowercase hex. Output length is always even (2 hex chars per byte); odd length requests are rounded up to the next even number.
5. Equivalent to Python `secrets.token_hex()` (for 64 chars: `secrets.token_hex(32)`) or `openssl rand -hex 32`.

#### Shared behaviour (all modes)

- Secret displayed in a read-only `<input type="text">` with monospace font.
- "Copy" button writes to `navigator.clipboard.writeText()`. A 30s timeout auto-clears the clipboard by writing an empty string.
- "Regenerate" button re-runs generation with the same mode and parameters.
- A visual strength bar (red/yellow/green) maps to entropy thresholds (<40, 40–80, >80 bits).
- Secrets are never stored in state management, never persisted, never sent to backend.
- If `navigator.clipboard` is unavailable: "Copy" button hidden, fallback text "Select and copy manually".
- The tool is still subject to RBAC (enable/disable, role permissions) via its `ToolModule` DB row.

---

## 5. CSRF Handling

For every state-changing request (POST, PUT, DELETE, PATCH):
1. Read `sakn_csrf` cookie value (JavaScript-accessible, NOT httpOnly).
2. Send as `X-CSRF-Token` header.
3. On 403 response: re-fetch CSRF cookie (lazy-set endpoint) and retry once.

---

## 6. i18n

- Library: react-i18next, namespaces lazily loaded.
- Resources bundled with the app (no runtime HTTP fetch).
- Language detection: cookie (visitors) or API response (authenticated users).
- Fallback: English (`en`).
- All user-facing strings wrapped in `t()`.
- Backend errors carry `message_key` that the frontend translates using the `errors` namespace.

---

## 7. Theming

- Tailwind `darkMode: 'class'` — a `dark` class on `<html>` toggles dark mode.
- `themeStore` values: `light`, `dark`, `system`.
- `system` uses `matchMedia('(prefers-color-scheme: dark)')` listener.
- Colors via CSS custom properties (Tailwind `theme.extend.colors`).

---

## 8. RTL Support

- Use CSS logical properties everywhere: `ps-4` not `pl-4`, `text-start` not `text-left`.
- Radix UI components wrapped in `dir` context (ltr/rtl).
- `dir` attribute on `<html>` toggled based on selected language.
- Visual regression tests must include RTL mode.
