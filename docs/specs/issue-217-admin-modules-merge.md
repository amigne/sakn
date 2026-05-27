# Spec: Admin Modules/Access Merge (#217)

## 1. Current State

Two separate admin pages manage the same concern (tool access):

| Page | Route | What it controls | API |
|---|---|---|---|
| AdminModulesPage | `/admin/modules` | Global module enable/disable | `GET /admin/modules`, `PUT /admin/modules/{name}` |
| AdminAccessPage | `/admin/access` | Tool access per role (allowed/denied) | `GET /admin/role-permissions`, `PUT /admin/role-permissions` |

AdminLayout has 6 tabs: Users, **Access**, Rate Limits, **Modules**, Settings, Logs.

### Data models involved

**ToolModule** (DB table `tool_modules`): `id`, `name`, `enabled`, `display_name_key`, `description_key`, `version`.

**RoleToolPermission** (DB table `role_tool_permissions`): `id`, `role` (visitor/authenticated/administrator), `tool_id` (FK → tool_modules), `allowed` (bool).

**GlobalSetting** (DB table `global_settings`): `key`, `value`. Module settings use prefix `module.{name}.` (e.g., `module.dns_lookup.`).

### Current API responses

`GET /admin/modules` returns:
```json
{ "modules": [{ "id", "name", "display_name_key", "description_key", "enabled", "version" }] }
```

`GET /admin/role-permissions` returns:
```json
{ "permissions": [{ "id", "role", "tool_id", "tool_name", "allowed" }] }
```

## 2. Target State

Single page at `/admin/modules` with a matrix table:

```
| Tool            | Enabled | Administrator | Authenticated | Visitor | Settings |
|-----------------|---------|---------------|---------------|---------|----------|
| DNS Lookup      | [O]     | [O]           | [O]           | [O]     | ⚙        |
| Ping            | [O]     | [O]           | [O]           | [O]     |          |
| TLS Cert Viewer | [O]     | [O]           | [O]           | [O]     |          |
| Traceroute      | [O]     | [O]           | [O]           | [O]     | ⚙        |
```

Each `[O]` is a `<ToggleSwitch>`.

### Business rules

1. **"Enabled" OFF** → the 3 role toggles on the same row become **disabled** (greyed out, `aria-disabled="true"`). Their backend `allowed` values are **preserved** — not set to false, just non-editable until re-enabled.
2. **"Enabled" ON** → role toggles become editable again, restoring their previous values.
3. **Settings gear (⚙)** appears only for modules that have `GlobalSetting` entries matching `module.{name}.%`. Opens the existing settings modal (DNS presets or Traceroute settings).
4. The `/admin/access` route is removed from the menu and redirects to `/admin/modules`. Backend endpoints are NOT deleted.

## 3. Technical Spec

### Data fetching

Client-side merge: call both `GET /admin/modules` and `GET /admin/role-permissions` in parallel, merge in the component. No new endpoint needed.

However, the "has settings" check currently hardcoded as `name === "dns_lookup" || name === "traceroute"` should be data-driven. **Small backend change**: add `has_settings: bool` to the `GET /admin/modules` response, computed by checking `GlobalSetting.key LIKE 'module.{name}.%'`.

### Components reused

- `<ToggleSwitch>` — existing component for all toggles
- `<table>` + Tailwind — same pattern as current AdminModulesPage and AdminAccessPage
- `<Modal>` — existing component for settings (unchanged)
- `<AdminLayout>` — existing layout wrapper

### Routes & navigation

- `/admin/modules` → new `AdminModulesPage` (matrix)
- `/admin/access` → `<Navigate to="/admin/modules" replace />` (redirect)
- AdminLayout: remove the "Access" tab (index 1), keep "Modules" tab
- Router: replace `AdminAccessPage` import with a redirect

### Backend changes

**`admin_modules.py` — `list_modules` endpoint**:
Add `has_settings` field by checking `GlobalSetting` for each module:

```python
# After fetching modules, check which have settings
from app.models.preferences import GlobalSetting
module_names = [m.name for m in modules]
settings_rows = await session.execute(
    select(GlobalSetting.key).where(
        GlobalSetting.key.like(f"{MODULE_SETTING_PREFIX}%")
    )
)
settings_modules = set()
for row in settings_rows.scalars().all():
    # Extract module name from key: "module.dns_lookup.xxx" -> "dns_lookup"
    rest = row[len(MODULE_SETTING_PREFIX):]
    mod_name = rest.split(".")[0]
    settings_modules.add(mod_name)
```

Add `"has_settings": m.name in settings_modules` to each module dict.

No new endpoint. No endpoint deletion.

### Frontend changes

**`AdminModulesPage.tsx`** — complete rewrite:
1. Fetch modules + permissions in parallel on mount
2. Merge data: for each module, find its 3 role permissions
3. Render matrix table
4. Toggle `Enabled`: call `updateModule()`, update local state, role toggles react to `module.enabled`
5. Toggle role: call `updateRolePermissions()`, optimistic update
6. Settings button: opens existing modals (DNS presets / Traceroute settings) — unchanged

**`Router.tsx`**:
- Replace `AdminAccessPage` import with `Navigate` import
- Change `/admin/access` route to `<Route path="/admin/access" element={<Navigate to="/admin/modules" replace />} />`

**`AdminLayout.tsx`**:
- Remove `{ key: "admin.access", to: "/admin/access" }` from `ADMIN_TAB_KEYS`

**Files NOT touched:**
- `AdminAccessPage.tsx` — kept but unused (can be deleted later)
- `admin_tools.py` — endpoints intact
- `admin_modules.py` — only `list_modules` gets a `has_settings` field

## 4. Acceptance Criteria

1. The matrix table at `/admin/modules` shows all modules with columns: Tool, Enabled, Administrator, Authenticated, Visitor, Settings.
2. Toggling "Enabled" off greys out the 3 role toggles on that row without modifying backend role permissions.
3. Toggling "Enabled" back on restores editable state for the role toggles, with their previous values preserved.
4. The Settings gear only appears for modules with `has_settings: true`.
5. `/admin/access` redirects to `/admin/modules`. The "Access" tab is removed from the admin menu.
6. All existing module settings (DNS presets, Traceroute show_private_hops) continue to work through the gear icon.

## 5. Implementation Plan

### Step 1 — Backend: add `has_settings` to `GET /admin/modules`
- `src/backend/app/api/v1/endpoints/admin_modules.py` — `list_modules` function
- Add test in `tests/integration/test_admin_modules.py`

### Step 2 — Frontend: rewrite `AdminModulesPage` with matrix
- `src/frontend/src/pages/admin/AdminModulesPage.tsx` — complete rewrite
- Fetch modules + permissions, merge, render matrix

### Step 3 — Frontend: update routes and menu
- `src/frontend/src/Router.tsx` — redirect `/admin/access` → `/admin/modules`
- `src/frontend/src/components/admin/AdminLayout.tsx` — remove "Access" tab

### Step 4 — Tests
- Backend: check `has_settings` in module list response
- Frontend: vitest on AdminModulesPage (disabled toggles, toggle behavior)
- E2E: login admin → navigate `/admin/modules` → verify matrix renders → toggle module off → verify role toggles disabled
