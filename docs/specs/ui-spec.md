# UI/UX Specification — SAKN

> **Version:** 2.0 — Condensed
> **Status:** Draft
> **Date:** 2026-05-14

Defines visual design, layout, navigation, interaction patterns, responsive behavior, and accessibility. For the API contract between frontend and backend, see `docs/specs/technical/spec-api-contract.md`. For tool execution protocols, see `spec-tools-live.md` and `spec-tools-instant.md`.

---

## 1. Design Principles

1. **Professional and sober**: Targets network engineers. Clean, dense, information-rich. No decorative elements.
2. **Clarity over originality**: Established UI patterns only. Forms, buttons, tables, navigation behave as expected.
3. **Compact layout**: Usable in a corner of the screen (~800px wide baseline). High information density, readable.
4. **Predictable tool behavior**: Parameters and defaults match CLI conventions.
5. **Progressive disclosure**: Advanced parameters (DSCP, DF bit) hidden behind expandable "Advanced" section. Recursive CNAME is ON by default for DNS.
6. **Error transparency**: User must understand what happened and what to do next.
7. **RTL compatibility from the start**: CSS logical properties everywhere, no hardcoded left/right.

### Visual Style

- **Typography**: Monospace for tool output (code/terminal). Sans-serif for UI chrome.
- **Color palette**: Limited. Primary for actions. Neutral backgrounds. Semantic: green (success), red (error), yellow (warning), blue (info).
- **Icons**: Simple, semantic (feather-style). Aid scanning, not decoration.
- **Spacing**: Compact (4px/8px increments). Thin borders (1px).

---

## 2. Site Structure and Navigation

### 2.1 Global Layout

```
+--------------+----------------------------------------------------+
| [Logo/Brand] |                        [Lang] [Theme] [User menu]  |  <- Top bar
+--------------+----------------------------------------------------+
| [Tool List]  | [Tool content area -- varies by tool and view]     |
| - Ping       |                                                    |
| - Traceroute |                                                    |
| - DNS        |                                                    |
| - TLS        |                                                    |
| [Admin]      |                                                    |
+--------------+----------------------------------------------------+
| [Footer: version, copyright]                                      |
+-------------------------------------------------------------------+
```

- **Sidebar**: Tool list (Ping | Traceroute | DNS Lookup | TLS/SSL). Admins see "Administration" pinned at bottom.
- **Disabled tools**: removed from sidebar entirely (not grayed out).
- **Admin sub-navigation**: horizontal tab bar within content area (Users | Rate Limits | Modules | Settings | Logs). Access rights are managed within the Modules page.

### 2.2 Routing

| Route | View | Access |
|---|---|---|
| `/` or `/ping` | Ping | All (if enabled) |
| `/traceroute` | Traceroute | All (if enabled) |
| `/dns` | DNS Lookup | All (if enabled) |
| `/ssl` | TLS/SSL Certificate | All (if enabled) |
| `/login` | Login | Visitors only |
| `/register` | Registration | Visitors only |
| `/verify-email?token=...` | Email verification | Visitors |
| `/reset-password` | Password reset request | Visitors |
| `/reset-password?token=...` | Password reset form | Visitors |
| `/account/preferences` | Preferences | Authenticated |
| `/account/sessions` | Sessions | Authenticated |
| `/account/delete` | Account deletion | Authenticated |
| `/admin/users` | User list | Admin |
| `/admin/users/{id}` | User detail | Admin |
| `/admin/modules` | Module activation & access rights | Admin |
| `/admin/rate-limits` | Rate limits | Admin |
| `/admin/modules` | Module activation | Admin |
| `/admin/settings` | Global settings | Admin |
| `/admin/logs` | Log viewer | Admin |

### 2.3 Auth Guarding

- Tool routes: accessible to all roles if tool enabled. Visitors lacking permission see "Tool not available" with login/register suggestion.
- Admin routes: admin only. Others see 403.
- Auth routes: visitors only. Authenticated users redirected to `/ping`.

---

## 3. Screen Inventory

### Public Screens

| ID | Name | Purpose |
|---|---|---|
| SCR-01 | Ping Tool | Execute ping, view results |
| SCR-02 | Traceroute Tool | Execute traceroute, view results |
| SCR-03 | DNS Lookup Tool | Execute DNS lookup, view results |
| SCR-04 | TLS/SSL Certificate Viewer | Fetch and display certificate chain |
| SCR-05 | Tool Not Available | Tool disabled or permission denied |
| SCR-06 | 404 Not Found | Unknown route |
| SCR-07 | 403 Forbidden | Admin area for non-admins |

### Auth Screens

SCR-08 Login | SCR-09 Registration | SCR-10 Email Verification | SCR-11 Verification Sent | SCR-12 Verification Success | SCR-13 Verification Expired | SCR-14 Password Reset Request | SCR-15 Password Reset Form | SCR-16 Password Reset Success

### Account Screens (Authenticated)

SCR-17 Preferences | SCR-18 Active Sessions | SCR-19 Account Deletion

### Admin Screens (Admin only)

SCR-20 User List | SCR-21 User Detail | SCR-22 Access Rights | SCR-23 Rate Limits | SCR-24 Module Activation | SCR-25 Log Viewer | SCR-26 Global Settings

---

## 4. Common Tool Interaction Pattern

### 4.1 Layout

Each tool screen: **Parameters Panel** (top) + **Output Panel** (bottom). Both visible simultaneously on desktop.

- Basic parameters always visible. Advanced parameters in expandable "Advanced" section.
- Default values pre-filled. "Start" button = primary action (accent color). "Reset" reverts to defaults. Enter triggers Start.
- Output panel: empty state ("Enter a target and click Start"), loading state (progress + elapsed time), results state (structured display), error state (banner).

### 4.2 Continuous vs Instant Tools

**Instant tools** (DNS, TLS): Start button → disabled with spinner → HTTP request → render result → re-enable button. Error re-enables button and displays in output panel.

**Continuous tools** (Ping, Traceroute): Start button → transforms to red "Stop" button → WebSocket streaming → results appear incrementally → Stop button or completion reverts to Start. Navigation away = implicit stop. Partial results retained with "Execution stopped by user" note.

### 4.3 Disabled States

- Tool disabled (globally or per role): sidebar entry not rendered. Direct URL shows "Tool not available."
- Form field not applicable (e.g., Port when ICMP protocol selected): grayed out + note explaining why.

---

## 5. Tool-Specific Output Displays

### 5.1 Ping Output

Table/Text toggle. Copy button in output panel header.

**Table view**:
```
Seq | Status    | RTT (ms) | TTL
----+-----------+----------+-----
 1  |   OK      |  12.3    |  64
 2  |   OK      |  11.8    |  64
 3  |  Timeout  |    -     |  -
 4  |   OK      |  13.1    |  64
```

**Text view**:
```
Reply from 8.8.8.8: bytes=56 time=12.3ms TTL=64
Reply from 8.8.8.8: bytes=56 time=11.8ms TTL=64
Request timeout for icmp_seq 3
Reply from 8.8.8.8: bytes=56 time=13.1ms TTL=64
```

**Summary** (after completion) — Table view:
```
Packets:
| Sent | Received | Lost |
|    4 |        3 |    1 |
| 100% |      75% |  25% |

RTT:
| Minimum | Average | Maximum | Std deviation |
| 11.8 ms | 12.4 ms | 13.1 ms |           0.5 |
```

**Summary** (after completion) — Text view:
```
Packets: sent = 4, received = 3 (75%), lost = 1 (25%)

Approximate round trip times in milliseconds:
    Minimum = 11.8ms, Maximum = 13.1ms, Average = 12.4ms, Std deviation = 0.5
```

All lost → only Packets table, "No RTT statistics available."

### 5.2 Traceroute Output

Table/Text toggle. Copy button. Rows appear incrementally. Destination row highlighted (subtle green).

**Table view**:
```
Hop | IP           | Hostname    | Probe 1 | Probe 2 | Probe 3
----+--------------+-------------+---------+---------+--------
 1  | 192.168.1.1  | router.home |  2.3ms  |  2.1ms  |  2.5ms
 2  | 10.0.0.1     | gw.isp.net  | 15.2ms  | 14.8ms  |  *
 3  | 72.14.237.1  | *           | 22.1ms  | 21.9ms  | 22.4ms
 4  | 8.8.8.8      | dns.google  | 12.1ms  | 11.9ms  | 12.3ms  <- Destination
```

- `*` = no response. Multipath = additional rows with "Multipath" note.
- DNS Resolution toggle off → IPs without hostnames.

### 5.3 DNS Lookup Output

Grouped cards, one per record type: A, AAAA, CNAME, MX, NS, TXT, SRV, SOA, PTR, CAA. Empty type → "No [type] records found." CNAME chain card when recursive resolution enabled. Copy button.

```
+------------------------------------------------------------------+
| A Records                                                         |
|   example.com.   TTL: 300   192.0.2.1                            |
|   example.com.   TTL: 300   192.0.2.2                            |
+------------------------------------------------------------------+
| CNAME Chain (Recursive)                                           |
|   www.example.com. -> example.com.                                |
|   example.com. -> A 192.0.2.1 (terminal)                         |
+------------------------------------------------------------------+
```

### 5.4 TLS/SSL Certificate Viewer Output

Structured cards. Copy button. Each certificate in the chain: collapsible section with subject, issuer, validity, SANs, key algorithm/size, fingerprints, extended key usage. Errors in RED: expired, name mismatch, self-signed, untrusted root, weak key (< 2048 bits RSA). Full chain valid → green "Chain valid" badge.

---

## 6. Responsive Behavior

| Breakpoint | Width | Layout |
|---|---|---|
| Desktop | >= 1024px | Sidebar expanded, parameters top / output bottom |
| Tablet | 768-1023px | Sidebar folded (icons only), parameters collapsible |
| Mobile | < 768px | Hamburger menu, single-column stacked, parameters auto-collapse on start |

**Compact mode** (~800px): Desktop layout with reduced parameter panel width. Labels may wrap/abbreviate. Tables use 0.9rem font.

**Mobile tables**: card-style layout instead of horizontal scroll. Text toggle available as alternative for Ping/Traceroute.

---

## 7. Visual Design

### 7.1 Color Palette

**Light mode**:
| Role | Color |
|---|---|
| Page background | #f5f5f5 |
| Card background | #ffffff |
| Primary text | #1a1a1a |
| Secondary text | #666666 |
| Border | #d0d0d0 |
| Primary action | #2563eb / hover #1d4ed8 |
| Success | #16a34a |
| Warning | #d97706 |
| Error | #dc2626 |
| Info | #2563eb |

**Dark mode**:
| Role | Color |
|---|---|
| Page background | #1a1a1a |
| Card background | #2a2a2a |
| Primary text | #e5e5e5 |
| Secondary text | #999999 |
| Border | #404040 |
| Primary action | #3b82f6 / hover #60a5fa |
| Success | #22c55e |
| Warning | #f59e0b |
| Error | #ef4444 |
| Info | #3b82f6 |

### 7.2 Theme

Three modes: Light, Dark, System (`prefers-color-scheme`). Default: System. Theme toggle: icon button in top bar, cycles or dropdown. Apply immediately via CSS custom properties. See `spec-frontend.md` §7 for implementation.

### 7.3 Language Switcher

Top bar, next to theme toggle. Displays two-letter code (EN/FR). Changes UI immediately. See `spec-frontend.md` §6 for implementation.

---

## 8. Error States and Messages

### 8.1 Display Methods

| Error Type | Display | Example |
|---|---|---|
| Form validation | Inline below field, red text | "Target is required." |
| Security filter / Tool execution / Network | Error banner in output panel | "Target not allowed." |
| Rate limit exceeded | Error banner + countdown timer | "Rate limit exceeded. Try again in 45 seconds." |
| Authentication | Inline or banner | "Invalid email or password." |
| Session expired | Redirect to login + banner | "Your session has expired." |
| Tool disabled / Permission denied | Full-page message | "This tool is currently disabled." |

### 8.2 Error Banner Design

Red background/border, exclamation icon. Dismissible (except persistent errors like rate limits). Warning states use yellow: rate limit >80% approaching, DNS no records, cert validation warnings.

---

## 9. Administration Panel

### 9.1 Layout

Same top bar + sidebar as main app. Admin sub-navigation via horizontal tab bar in content area. "Administration" entry in sidebar marked active.

### 9.2 Sub-sections

**User Management**: searchable, filterable (status, role), sortable user table. Paginated (50/page). User detail: info card + action buttons (block/unblock, lock/unlock, delete) + internal notes (admin-only).

**Access Rights**: matrix — rows = tools, columns = roles. Each cell = toggle switch. Changes save immediately. Integrated into the Modules page.

**Rate Limiting**: two tables.
  - *Global limits*: rows = roles, columns = Soft limit (/s) + Hard limit (/h). Soft limit = requests per second (short window, 1s). Hard limit = requests per hour (long window, 1h). Exceeding either blocks the user. Cells editable (click-to-edit, blur-to-save).
  - *Per-tool limits*: optional overrides for specific tools. Rows = role + tool pairs, with an add-row form at the top of the table. Role + tool pair must be unique. Columns = Role, Tool, Soft limit (/s), Hard limit (/h), Delete button. Validation: per-tool ≤ global for the same role. "Reset to defaults" button restores both tables.

**Module Activation**: table — rows = tools, columns = Enabled toggle (centered), Settings gear icon (centered). DNS Lookup settings: editable table of DNS server presets (IP + Description), with add/edit/delete/reorder. IP addresses validated as IPv4 before saving. Adding a preset keeps the modal open to show the updated list. Defaults: Google (8.8.8.8), Cloudflare (1.1.1.1), Quad9 (9.9.9.9). Auto-save on each action.

**Access Rights** (within Modules page): matrix — rows = tools, columns = roles. Each cell = toggle switch. Changes save immediately.

**Log Viewer**: filterable (date range, user, tool, event type), paginated table. Click row to expand full details. Auto-refresh with pause toggle.

**Global Settings**: log retention (days, default 90, min 1). Auto-save on blur.

### 9.3 Admin Guarding

Admin routes require admin role. Non-admins see 403. Admin sidebar entry only visible to admins.

---

## 10. Authentication Screens

### 10.1 Login (SCR-08)

Centered card, no top bar. Email + password fields, password visibility toggle (eye icon). "Sign In" button. Links: "Forgot password?" → reset request. "Don't have an account? Sign up" → registration. Error: "Invalid email or password."

### 10.2 Registration (SCR-09)

Centered card. Fields: Email, First Name, Last Name, Password, Confirm Password. Real-time password requirements checklist (8+ chars, uppercase, lowercase, digit). Password visibility toggle. On success: redirect to verification sent screen.

### 10.3 Email Verification

- **Verification Sent** (SCR-11): "A verification email has been sent to [email]." Resend option with 60s cooldown.
- **Success** (SCR-12): Green icon + "Email verified. You can now sign in." Link to login.
- **Expired** (SCR-13): Warning icon + "Send new verification link" button.

### 10.4 Password Reset

- **Request** (SCR-14): Email field + "Send Reset Link." Always returns same message: "If the email is registered, a reset link has been sent."
- **Reset Form** (SCR-15): New Password + Confirm Password. Same requirements checklist as registration. On success: redirect to login.

---

## 11. Accessibility Requirements

**Target**: WCAG 2.1 Level AA.

**Keyboard**: All interactive elements reachable via Tab in logical order. Custom components (toggles, dropdowns, accordions) support Enter/Space/Arrow keys. Visible focus ring (2px offset, high contrast). No tab traps.

**Screen readers**: All inputs have `<label>`. WebSocket streaming results use `aria-live` regions (polite for updates, assertive for errors). Tables have proper `<th>` with scope. Icon buttons have `aria-label`.

**Contrast**: 4.5:1 normal text, 3:1 large text. Semantic colors accompanied by icons/text. Both themes independently compliant.

**Reduced motion**: Respect `prefers-reduced-motion`. Simplify non-essential animations (spinners/progress bars remain active).

**Zoom**: Usable at 200% without horizontal scroll. Touch targets ≥ 44×44px.

**Focus management**: After form submit → output panel or first error. After modal close → triggering element. SPA route change → top of new view.

**Testing checklist** (per screen): keyboard-only navigation, screen reader, contrast (both themes), 200% zoom, reduced motion.

---

## 12. Wireframes

### 12.1 Ping Tool — Desktop (Reference Layout)

All tool screens follow this pattern: sidebar (left) + parameters (content top) + output (content bottom).

```
+--------------+----------------------------------------------------+
| [Logo/Brand] |                        [EN v] [    ] [User v]     |
+--------------+----------------------------------------------------+
| [Ping]       | Ping                                              |
| [Traceroute] | Target:          [8.8.8.8           ]             |
| [DNS]        | Count:           [4] (1-100)                      |
| [TLS]        | Timeout (s):     [10] (1-60)                      |
| [Admin]      | Packet Size:     [56] (8-65507 bytes)             |
|              |                                                    |
|              | Advanced v                                         |
|              |   DF Bit: [ ]   DSCP: [0]   Max Duration: [30]    |
|              | [Start]  [Reset]  [Table v] [Text]                 |
|              |----------------------------------------------------|
|              | [Status: Running... packet 2 of 4]  [Cancel] [Copy]|
|              |                                                    |
|              | Seq | Status    | RTT (ms) | TTL                   |
|              |-----+-----------+----------+-----                  |
|              |  1  |  OK       |  12.3    |  64                   |
|              |  2  |  OK       |  11.8    |  64                   |
|              | ...                                              |
|              |                                                    |
|              | ## Packets                                        |
|              | Sent: 4 | Received: 3 | Lost: 1 (25%)             |
|              | RTT: Min 11.8 | Avg 12.4 | Max 13.1 | StdDev 0.5 |
+--------------+----------------------------------------------------+
| [Footer]                                                         |
+-------------------------------------------------------------------+
```

### 12.2 Admin — User List (Reference Admin Layout)

Admin screens follow this pattern: admin tabs (below top bar) + content area.

```
+--------------+----------------------------------------------------+
| [Logo/Brand] |                        [EN v] [    ] [User v]     |
+--------------+----------------------------------------------------+
| [Ping]       | [Users] - [Rate Lim] - [Modules] - [Settings] - [Logs] |
| [Traceroute] | User Management                                    |
| [DNS]        |                                                    |
| [TLS]        | Search: [________]  Status: [All v]  Role: [All v] |
| [Admin]*     |                                                    |
|              | Email           | Status   | Role  | Joined   | Actions |
|              |-----------------+----------+-------+----------+--------|
|              | alice@acme.com  | Verified | Auth  | 2026-01-15| [View] |
|              | bob@acme.com    | Blocked  | Auth  | 2026-02-20| [View] |
|              | ...                                                 |
|              | << Prev  1 2 3 ... 10  Next >>                     |
+--------------+----------------------------------------------------+
| [Footer]                                                         |
+-------------------------------------------------------------------+
```

---

## 13. Resolved UX Questions

| ID | Question | Decision |
|---|---|---|
| UI-OQ-01 | Copy to clipboard button? | Yes, for both structured and text views. |
| UI-OQ-02 | Raw PEM data for TLS certs? | Yes, collapsible section. |
| UI-OQ-03 | Sort/filter DNS results? | No, static results. |
| UI-OQ-04 | "Quick Ping" in top bar? | No, keep toolbar clean. |
| UI-OQ-05 | Log viewer live "tail" mode? | Yes, auto-refresh with pause toggle. |
| UI-OQ-06 | Error codes in messages? | Yes, expandable technical detail. |
| UI-OQ-07 | Tooltip on truncated table cells? | Yes. |
