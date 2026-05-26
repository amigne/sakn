# Accessibility Audit — WCAG 2.1 Level AA

> **Version:** 1.0 — New document
> **Status:** Draft
> **Date:** 2026-05-26
> **Issue:** #7

## 1. Scope

Audit the SAKN frontend against WCAG 2.1 Level AA on the following criteria:

| Criterion | Description | Tool |
|---|---|---|
| 1.4.3 Contrast (Minimum) | 4.5:1 normal text, 3:1 large text | axe-core |
| 1.4.4 Resize text | 200% zoom without horizontal scroll | Manual + Playwright |
| 2.1.1 Keyboard | All interactive elements reachable via Tab | Manual + Playwright |
| 2.4.3 Focus Order | Focus order matches visual order | Manual + Playwright |
| 2.5.5 Target Size | Touch targets ≥ 44×44px | axe-core |
| 2.4.7 Focus Visible | Visible focus indicator on all interactive elements | Manual |
| 4.1.1 Parsing | No duplicate IDs, valid ARIA roles | axe-core |
| 4.1.2 Name, Role, Value | All UI components have accessible names | axe-core |
| 2.3.1 Three Flashes | No more than 3 flashes per second | N/A (no animations) |

## 2. Screens to Audit

| Screen | Route | Mode |
|---|---|---|
| Login | `/login` | Unauthenticated |
| Register | `/register` | Unauthenticated |
| Reset Password | `/reset-password` | Unauthenticated |
| Verify Email | `/verify-email` | Unauthenticated |
| No Tools (visitor) | `/no-tools` | Unauthenticated |
| Ping | `/ping` | Authenticated |
| DNS Lookup | `/dns-lookup` | Authenticated |
| SSL Viewer | `/ssl-viewer` | Authenticated |
| Traceroute | `/traceroute` | Authenticated |
| Profile | `/profile` | Authenticated |
| Sessions | `/sessions` | Authenticated |
| Delete Account | `/delete-account` | Authenticated |
| Admin Users | `/admin/users` | Admin |
| Admin User Detail | `/admin/users/:id` | Admin |
| Admin Access | `/admin/access` | Admin |
| Admin Rate Limits | `/admin/rate-limits` | Admin |
| Admin Modules | `/admin/modules` | Admin |
| Admin Settings | `/admin/settings` | Admin |
| Admin Logs | `/admin/logs` | Admin |
| Privacy Policy | `/privacy` | Public |
| Forbidden (403) | `/forbidden` | Any |
| Not Found (404) | `/nonexistent` | Any |

## 3. Tools

- **axe-core**: Automated accessibility testing via `@axe-core/playwright`
- **Playwright**: Keyboard navigation, zoom, and screenshot comparison
- **Manual checklist**: Contrast verification in both light and dark themes

## 4. Acceptance Criteria

- 0 `serious` or `critical` violations per screen after fixes
- `moderate` and `minor` violations documented and tracked via follow-up issues
- Keyboard navigation reaches all interactive elements without traps
- 200% zoom does not cause horizontal scroll or content loss
- Focus indicators visible on all interactive elements

## 5. Audit Methodology

### 5.1 Automated (axe-core)

1. Install `@axe-core/playwright` as a dev dependency
2. Add `axe` fixture to Playwright config
3. For each screen, navigate and run `await new AxeBuilder({ page }).analyze()`
4. Export violations as JSON, attach to audit report
5. Categorize by severity: critical, serious, moderate, minor

### 5.2 Keyboard Navigation (manual + automated)

1. Navigate to each screen
2. Press Tab repeatedly and verify focus order
3. Check that no element is unreachable
4. Check that modals trap focus and restore on close
5. Verify skip-to-content link exists (if applicable)

### 5.3 200% Zoom (manual)

1. Set browser zoom to 200% (`page.evaluate(() => { document.body.style.zoom = '200%'; })`)
2. Verify no horizontal scrollbar appears
3. Verify all content remains readable

### 5.4 Contrast (automated + manual)

1. Run axe-core contrast checks in both light and dark themes
2. Manually verify `prefers-reduced-motion` disables animations

## 6. Reporting

- **Baseline**: Current violation count per screen (pre-fix) documented in PR body
- **Follow-up issues**: 1 issue per `serious`/`critical` violation, 1 grouping issue for `moderate`/`minor`
- **CI integration**: Add axe-core to the Playwright E2E workflow (non-blocking, report-only)
