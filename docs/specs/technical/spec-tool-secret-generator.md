# Secret Generator Tool Specification

> **Version:** 1.0
> **Status:** Final — Implemented (PR #434)
> **Date:** 2026-06-05
> **Module:** Secret Generator (`secret_generator`)
> **References:** `functional-spec.md` §3.7, `spec-api-contract.md` §6/§10.3, `ui-spec.md` SCR-28, ADR-017

The Secret Generator is a **frontend-only tool**: all generation happens client-side via the Web Crypto API. The backend is involved only for tool discovery (`GET /tools`) and admin management (enable/disable, permissions). There is no `POST /api/v1/tools/secret_generator/execute` endpoint — calling it returns **405 Method Not Allowed**.

---

## 1. Frontend-Only Tool Contract

### 1.1 `backend` field on `ToolDefinition`

A new field `backend: bool` (default `True`) is added to `ToolDefinition`:

```python
@dataclass
class ToolDefinition:
    name: str
    display_name_key: str
    description_key: str
    category: ToolCategory
    version: str
    parameters: list[ToolParameter] = field(default_factory=list)
    requires_privileges: list[str] = field(default_factory=list)
    backend: bool = True  # NEW — default True for backward compatibility
```

### 1.2 `to_api_definition()` serialization

`ToolDefinition.to_api_definition()` includes `backend` in the response:

```python
def to_api_definition(self) -> dict[str, Any]:
    d = self.get_definition()
    return {
        "name": d.name,
        "display_name_key": d.display_name_key,
        "description_key": d.description_key,
        "category": d.category.value,
        "version": d.version,
        "backend": d.backend,  # NEW
        "parameters": [...],
    }
```

### 1.3 `GET /tools` response

Frontend-only tools appear identically to backend tools in the `/tools` response, distinguished solely by `"backend": false`:

```json
{
  "tools": [
    {
      "name": "secret_generator",
      "display_name_key": "tools.secret_generator.name",
      "description_key": "tools.secret_generator.description",
      "category": "security",
      "version": "1.0.0",
      "backend": false,
      "parameters": [...]
    }
  ]
}
```

### 1.4 `POST /tools/{tool_name}/execute` for `backend: false` tools

If a tool has `backend: false`, the execute endpoint returns **405 Method Not Allowed**:

```
POST /api/v1/tools/secret_generator/execute
```

**Response** (405):
```json
{
  "error": {
    "code": "TOOL_IS_FRONTEND_ONLY",
    "message_key": "errors.tool_is_frontend_only",
    "message": "This tool runs entirely in the browser and has no backend execution endpoint.",
    "details": null
  }
}
```

The 405 is enforced in the execute route handler (`app/api/v1/endpoints/tools.py`, `execute_tool`), **not** by raising `NotImplementedError` in the tool class. The tool class never defines `execute()` — it is a pure definition holder.

Rationale: see ADR-017 §3.2.

---

## 2. Backend: `SecretGeneratorTool`

### 2.1 Definition

```python
from app.tools.base import BaseTool, ToolCategory, ToolDefinition, ToolParameter


class SecretGeneratorTool(BaseTool):
    """Frontend-only tool. No backend execution."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="secret_generator",
            display_name_key="tools.secret_generator.name",
            description_key="tools.secret_generator.description",
            category=ToolCategory.SECURITY,
            version="1.0.0",
            backend=False,
            parameters=[
                # Mode selector
                ToolParameter(
                    name="mode",
                    type="enum",
                    label_key="tools.secret_generator.mode_label",
                    description_key="tools.secret_generator.mode_desc",
                    required=True,
                    default="password",
                    constraints={
                        "options": ["password", "token", "hex"],
                        "option_labels": {
                            "password": "tools.secret_generator.mode_password",
                            "token": "tools.secret_generator.mode_token",
                            "hex": "tools.secret_generator.mode_hex",
                        },
                    },
                ),
                # Password mode
                ToolParameter(
                    name="length",
                    type="integer",
                    label_key="tools.secret_generator.param_length_label",
                    description_key="tools.secret_generator.param_length_desc",
                    required=True,
                    default=20,
                    constraints={"min": 8, "max": 128},
                ),
                ToolParameter(
                    name="uppercase",
                    type="boolean",
                    label_key="tools.secret_generator.param_uppercase_label",
                    description_key="",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="lowercase",
                    type="boolean",
                    label_key="tools.secret_generator.param_lowercase_label",
                    description_key="",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="digits",
                    type="boolean",
                    label_key="tools.secret_generator.param_digits_label",
                    description_key="",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="symbols",
                    type="boolean",
                    label_key="tools.secret_generator.param_symbols_label",
                    description_key="",
                    required=False,
                    default=True,
                ),
                # Token mode length (shared key prefix with password length but distinct range)
                ToolParameter(
                    name="token_length",
                    type="integer",
                    label_key="tools.secret_generator.param_length_token_label",
                    description_key="tools.secret_generator.param_length_token_desc",
                    required=False,
                    default=43,
                    constraints={"min": 16, "max": 256},
                ),
                # Hex mode length
                ToolParameter(
                    name="hex_length",
                    type="integer",
                    label_key="tools.secret_generator.param_length_hex_label",
                    description_key="tools.secret_generator.param_length_hex_desc",
                    required=False,
                    default=64,
                    constraints={"min": 16, "max": 512},
                ),
            ],
        )
```

Notes:
- Parameters are **descriptive only** — they document the tool's UI contract in `/tools`. The frontend reads them for dynamic form rendering.
- `execute()` is **not** overridden — the base class raises `NotImplementedError`, but the execute route handler catches `backend: false` before reaching `execute()` and returns 405 directly.
- `ToolCategory.SECURITY` already exists in `base.py`.

### 2.2 Registration & Seed

In `src/backend/app/main.py`, add:

```python
from app.tools.secret_generator import SecretGeneratorTool

# In the registry block:
registry.register(SecretGeneratorTool())
```

The existing seed loop (lines 111-134) handles `SecretGeneratorTool` automatically:
- Creates the `ToolModule` row (`name="secret_generator"`, `enabled=True`)
- Creates `RoleToolPermission` rows for all three roles with `allowed=True`

No migration needed: `ToolModule` table already exists. The new row is inserted on first boot after deployment.

### 2.3 Admin Integration

- The tool appears in Admin > Modules with an Enabled toggle.
- Permission matrix (visitor/authenticated/admin) works identically — toggling off a role removes the tool from that role's sidebar and `/tools` response.
- No status icon (no `has_status` flag — there is no backend state to report).
- No settings gear (no `has_settings` flag — there are no backend-configurable parameters).

---

## 3. Frontend: Client-Side Algorithms

### 3.1 CSPRNG Source

All randomness comes from `crypto.getRandomValues()` (Web Crypto API). **Never `Math.random()`.**

```typescript
function getRandomBytes(n: number): Uint8Array {
  const bytes = new Uint8Array(n);
  crypto.getRandomValues(bytes);
  return bytes;
}
```

### 3.2 Password Mode — Rejection Sampling

Algorithm: uniform random selection from the active character set union, with rejection sampling to eliminate modulo bias.

```
charset = (uppercase ? A-Z : "") + (lowercase ? a-z : "") + (digits ? 0-9 : "") + (symbols ? SYMBOLS : "")
max_valid = 256 - (256 % charset.length)  // largest multiple of charset.length ≤ 255

for i in 0..length:
  do:
    byte = getRandomBytes(1)[0]
  while byte >= max_valid
  secret[i] = charset[byte % charset.length]
```

**Edge case**: if `charset.length == 0` (all toggles off), no secret is generated. The UI displays the i18n message `tools.secret_generator.no_charset_selected`. This state is prevented at the UI level (last toggle snaps back).

**Entropy calculation**: `entropy_bits = length * log2(charset.length)`

**Symbol set**: Shell-safe subset of ASCII printable symbols (25 characters).
Characters that are shell meta-characters (backtick, pipe, redirect, single quote,
backslash, tilde, forward slash) are deliberately excluded to prevent copy-paste
hazards when secrets are used in terminal environments:
```
! @ # $ % ^ & * ( ) - _ = + [ ] { } ; : , . < > ?
```
Total: 25 characters.

**Rationale**: The full ASCII printable symbol set includes 32 characters, but 7 of
them are shell meta-characters that can cause dangerous copy-paste behavior:
`` ` `` (command substitution), `|` (pipe), `\` (escape), `'` (quote break),
`~` (home expansion), `/` (path separator).  The 25-char shell-safe subset avoids
this risk while reducing the total charset from 94 to 87 — an entropy difference
below 1 % for typical password lengths (e.g., 128 × log₂(87) ≈ 824 bits vs.
128 × log₂(94) ≈ 839 bits).

### 3.3 Token Mode — Base64url (RFC 4648 §5)

Base64url alphabet: `A-Z a-z 0-9 - _` (64 characters, each encodes 6 bits).

Algorithm:
```
byte_count = ceil(length * 6 / 8)
bytes = getRandomBytes(byte_count)
encoded = base64url_encode(bytes)   // no padding (= stripped)
secret = encoded.slice(0, length)   // trim to exactly `length` chars
entropy_bits = length * 6
```

`ceil(length * 6 / 8)` bytes always encode to **at least** `length` base64url characters (`ceil(4·byte_count/3) ≥ length`), so the trim yields **exactly** `length` characters. Output length therefore always equals the requested length — never shorter. Each character independently encodes 6 bits, so the trimmed token has `length * 6` bits of entropy.

**Entropy calculation**: `entropy_bits = length * 6`

**Default 43 chars → 258 bits**: `ceil(43 * 6 / 8) = 33 bytes → base64url = 44 chars → trimmed to 43 chars`. Entropy = `43 × 6 = 258` bits. The frontend displays "43 caractères (258 bits)."

### 3.4 Hex Mode — Lowercase Hexadecimal

Algorithm:
```
byte_count = ceil(length / 2)
bytes = getRandomBytes(byte_count)
secret = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')
actual_length = secret.length  // always even, always ≥ length
entropy_bits = actual_length * 4
```

Output is **always even** (each byte = 2 hex chars). An odd requested length is rounded up: `length=17` → `ceil(17/2)=9 bytes` → 18 chars. The frontend displays the actual length.

**Entropy calculation**: `entropy_bits = actual_length * 4`

**Default 64 chars → 256 bits**: `ceil(64/2) = 32 bytes → 64 hex chars`. 64 × 4 = 256 bits.

### 3.5 Strength Classification

```typescript
function classifyStrength(entropyBits: number): StrengthLevel {
  if (entropyBits >= 256) return "very_strong";
  if (entropyBits >= 128) return "strong";
  if (entropyBits >= 64) return "fair";
  return "weak";
}
```

| Label | Key | Entropy | Color |
|---|---|---|---|
| Weak | `tools.secret_generator.strength_weak` | < 64 bits | Red (`var(--color-error)`) |
| Fair | `tools.secret_generator.strength_fair` | 64–127 bits | Orange (`var(--color-warning)`) |
| Strong | `tools.secret_generator.strength_strong` | 128–255 bits | Blue (`var(--color-info)`) |
| Very Strong | `tools.secret_generator.strength_very_strong` | ≥ 256 bits | Green (`var(--color-success)`) |

Rationale for the 256-bit threshold: NIST SP 800-63B recommends ≥ 112 bits for memorized secrets. For machine-generated tokens (API keys, hex secrets), 256 bits is the industry standard (e.g., AES-256 key, Python `secrets.token_urlsafe(32)`).

---

## 4. Clipboard Management

### 4.1 Copy with Auto-Clear

```typescript
let clearTimer: ReturnType<typeof setTimeout> | null = null;

async function copyToClipboard(secret: string): Promise<void> {
  await navigator.clipboard.writeText(secret);
  // Reset previous timer
  if (clearTimer) clearTimeout(clearTimer);
  // Schedule auto-clear in 30s
  clearTimer = setTimeout(async () => {
    try {
      const current = await navigator.clipboard.readText();
      if (current === secret) {
        await navigator.clipboard.writeText("");  // Clear
      }
    } catch {
      // Clipboard read/write may fail — silent no-op
    }
  }, 30_000);
}
```

**Rationale**: 30 seconds gives the user time to paste the secret, while limiting exposure if the user forgets. The timer resets on each Copy click. Clearing only if the clipboard still contains the original secret avoids overwriting unrelated content.

### 4.2 Clipboard Unavailable

Detection: check `navigator.clipboard?.writeText` at mount time. If unavailable:
- Hide the "Copy" button.
- Display the hint `tools.secret_generator.clipboard_unavailable`.
- The secret field remains selectable for manual copy (Ctrl+C).

---

## 5. Files Touched (Sprint 1 — Backend Contract)

| File | Change |
|---|---|
| `src/backend/app/tools/base.py` | Add `backend: bool = True` to `ToolDefinition`; serialize in `to_api_definition()` |
| `src/backend/app/tools/secret_generator.py` | **New file**: `SecretGeneratorTool` class with `get_definition()` only |
| `src/backend/app/main.py` | Register `SecretGeneratorTool` in the registry (seed handled automatically) |
| `src/backend/app/api/v1/endpoints/tools.py` (`execute_tool`) | Guard: if tool has `backend: false`, return 405 before calling `execute()` |
| `src/backend/app/models/tool_module.py` | No change — `ToolModule` schema unchanged |
| `src/frontend/src/...` | **Not touched this sprint** — Sprint 2+ |

---

## 6. i18n Keys (Complete List)

Per `spec-api-contract.md` §10.3. All keys must exist in both `fr.json` and `en.json`.

```
tools.secret_generator.name
tools.secret_generator.description
tools.secret_generator.mode_label
tools.secret_generator.mode_desc
tools.secret_generator.mode_password
tools.secret_generator.mode_token
tools.secret_generator.mode_hex
tools.secret_generator.param_length_label
tools.secret_generator.param_length_desc
tools.secret_generator.param_length_token_label
tools.secret_generator.param_length_token_desc
tools.secret_generator.param_length_hex_label
tools.secret_generator.param_length_hex_desc
tools.secret_generator.param_uppercase_label
tools.secret_generator.param_lowercase_label
tools.secret_generator.param_digits_label
tools.secret_generator.param_symbols_label
tools.secret_generator.strength_weak
tools.secret_generator.strength_fair
tools.secret_generator.strength_strong
tools.secret_generator.strength_very_strong
tools.secret_generator.entropy
tools.secret_generator.copy
tools.secret_generator.regenerate
tools.secret_generator.copied
tools.secret_generator.clipboard_unavailable
tools.secret_generator.js_disabled
tools.secret_generator.no_charset_selected
tools.secret_generator.auto_clear_notice

errors.tool_is_frontend_only
```

---

## 7. No New Dependencies

- Web Crypto API (`crypto.getRandomValues`, `crypto.subtle`) is a browser standard, available in all modern browsers and secure contexts (HTTPS/localhost).
- Base64url encoding/decoding is implemented in userland (~10 lines of JavaScript) using `btoa` + character substitution, or standard `Uint8Array` manipulation.
- No external library required.

---

## 8. References

| Source | Sections |
|---|---|
| `functional-spec.md` | §3.7 (Secret Generator) |
| `spec-api-contract.md` | §6 (Tools), §10.3 (i18n keys) |
| `ui-spec.md` | SCR-28, §5.5 (Secret Generator output), §12.3 (wireframe) |
| `docs/adr/ADR-017-frontend-only-tool-pattern.md` | Architectural decision |
| `src/backend/app/tools/base.py` | `ToolDefinition`, `BaseTool`, `to_api_definition()` |
| `src/backend/app/main.py:90-147` | Registry + seed pattern |
