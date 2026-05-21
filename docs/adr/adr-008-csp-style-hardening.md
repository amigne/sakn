# ADR-008: CSP Style Hardening with style-src-elem / style-src-attr Split

## Status
Accepted — 2026-05-21

## Context
The current CSP uses `style-src 'self' 'unsafe-inline'` which allows both
inline `<style>` blocks and inline `style=""` attributes. The audit finding
M-2 flagged `'unsafe-inline'` as a medium-severity residual risk.

Three strategies were evaluated:

**(a) Nonces CSP** — Generate a nonce per request, inject it into `<style>`
tags. Rejected for this project: the frontend is a client-side SPA served as
static files by nginx. Injecting nonces would require Caddy-level HTML body
substitution (sub_filter/templates), adding latency and operational complexity.

**(b) Hashes CSP** — Compute SHA-256 hashes of all inline styles at build
time, inject into the CSP header. Rejected: the project uses Radix UI (Popper,
Select, Tooltip, etc.) which injects highly dynamic `style=""` attributes
(`left`, `top`, `transform`, `transform-origin`) via Floating UI. These values
change on every scroll and resize event and cannot be pre-hashed. CSP nonces
do not apply to `style=""` attributes — nonces only cover `<style>` blocks.

**(c) Eliminate inline styles** — Refactor to CSS modules or Tailwind-only.
Partial but insufficient: Tailwind v4 already handles the majority of styling.
The remaining application-level dynamic styles (ProgressBar width, password
strength bar) are percentage-driven and cannot be expressed as static utility
classes. More critically, Radix UI's Popper components require inline styles
for dynamic positioning — replacing them would mean rewriting Tooltip, Select,
and other core UI components.

## Decision
Use CSP Level 3's `style-src-elem` / `style-src-attr` split to narrow the
grant without breaking Radix UI:

- **`style-src-elem 'self'`** — Blocks all inline `<style>` blocks and
  `style=""` attributes on `<link rel="stylesheet">` elements. Only external
  `.css` files served from the same origin are allowed. This is the directive
  that protects against CSS injection via `<style>` tags.

- **`style-src-attr 'unsafe-inline'`** — Allows inline `style=""` attributes
  on individual DOM elements. This is needed for Radix UI Popper (dynamic
  positioning), ProgressBar/PasswordStrengthIndicator (dynamic widths), and
  any future UI library that uses inline styles for layout.

- **Remove the `style-src` fallback** — When present, `style-src` acts as a
  fallback for both `style-src-elem` and `style-src-attr`. Removing it ensures
  the split directives take full effect with no ambiguity.

Additionally, add three defense-in-depth hardening directives:

- **`object-src 'none'`** — Block all plugins (Flash, Java applets). These are
  legacy vectors but `object-src` should never fall through to `default-src`.
- **`base-uri 'self'`** — Prevent `<base>` tag injection, which could hijack
  relative URL resolution for scripts, styles, and form submissions.
- **`frame-ancestors 'none'`** — Block all framing (complements
  `X-Frame-Options: DENY` with browser-native CSP enforcement, also prevents
  drag-and-drop framing attacks that bypass `X-Frame-Options`).

Full CSP after this ADR:
```
default-src 'self'; script-src 'self'; style-src-elem 'self';
style-src-attr 'unsafe-inline'; img-src 'self' data:;
connect-src 'self' ws: wss:; form-action 'self';
object-src 'none'; base-uri 'self'; frame-ancestors 'none'
```

Browser support: `style-src-elem` and `style-src-attr` are CSP Level 3
(Chrome 59+, Firefox 58+, Safari 12.1+, Edge 79+). Browsers that do not
support them fall back to `default-src 'self'` for styles, which is
stricter — inline styles would be entirely blocked on those browsers. This
is an acceptable degradation (mispositioned tooltips on pre-2018 browsers).

## Consequences

- Inline `<style>` blocks are blocked at the CSP level. If a dependency or
  future code introduces one, it will be blocked and visible via a console
  CSP violation report.
- Radix UI Popper, Select, Tooltip continue to function via
  `style-src-attr 'unsafe-inline'`.
- `object-src 'none'` provides defense-in-depth against legacy plugin attacks.
- `base-uri 'self'` prevents `<base>` tag injection attacks.
- `frame-ancestors 'none'` complements `X-Frame-Options: DENY` with
  CSP-native enforcement.
- Audit finding M-2 is mitigated: `'unsafe-inline'` is removed from the
  element-level style directive. The attribute-level directive retains it
  with an explicit, documented justification.
- Residual risk: `style-src-attr 'unsafe-inline'` still allows CSS attribute
  selectors via injected style attributes. However, injecting a `style`
  attribute requires an existing script execution vulnerability, which is
  blocked by `script-src 'self'` (no `'unsafe-inline'`, no `'unsafe-eval'`).

## Rollback
1. Revert `_CSP_HEADER` in `security_headers.py` and CSP line in `Caddyfile`
   to the previous `style-src 'self' 'unsafe-inline'` value.
2. Restart backend and Caddy.
3. No database migration, no frontend rebuild needed.
