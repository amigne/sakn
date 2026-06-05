# ADR-017: Frontend-Only Tool Pattern

## Status
Proposed — 2026-06-05

## Context

SAKN's tool model (`ToolDefinition`, `BaseTool`, `ToolRegistry`) assumes every tool has a backend execution endpoint: `POST /api/v1/tools/{tool_name}/execute`. The Secret Generator (`secret_generator`) is the first tool that runs **entirely client-side** — all generation uses the Web Crypto API in the browser. No secret is ever sent to the backend.

We need a pattern for modeling tools that:
1. Appear in `GET /tools` (so the frontend discovers them and renders them in the sidebar).
2. Appear in Admin > Modules (so admins can enable/disable and manage role permissions).
3. Have **no backend execution endpoint** (calling `POST .../execute` must fail cleanly with a clear error).
4. Are indistinguishable from backend tools from the frontend's perspective (except for a `backend: false` flag that tells the frontend not to make an execute request).

## Decision

**Add a `backend: bool` field (default `True`) to `ToolDefinition` and expose it in `to_api_definition()`. Frontend-only tools set `backend=False` and never override `execute()`. The execute route handler detects `backend: false` and returns 405 Method Not Allowed.**

### 3.1 Flag Shape: `backend: bool` on `ToolDefinition`

**Decision**: A single boolean field `backend: bool` (default `True`) on the `ToolDefinition` dataclass.

**Rationale**:
- Minimal change — one field, backward-compatible default.
- The name `backend` directly answers the question "does this tool run on the backend?". It's the term already used in `spec-api-contract.md` line 428.
- A boolean is sufficient — we don't need an enum because there's no third category in the current roadmap. If a future tool has a hybrid execution model (e.g., client-side generation + backend validation), we can evolve to `execution_model: "backend" | "frontend" | "hybrid"` without breaking existing tools.

**Alternatives considered and rejected**:
- `execution: "backend" | "frontend"` string enum: Over-engineered for two states. A boolean is simpler and the migration path to an enum is trivial.
- `is_frontend_only: bool`: Negation is harder to read. `backend: true` reads naturally as "this tool runs on the backend."
- Separate `FrontendOnlyTool` base class: Adds a parallel class hierarchy for no benefit. A single field is simpler.
- Separate frontend-only tool registry or config file: Loses admin visibility and role-based access control. Tools must be in the same registry to benefit from the existing seed, admin, and permission infrastructure.

### 3.2 HTTP Code for `execute`: 405 Method Not Allowed

**Decision**: `POST /api/v1/tools/{tool_name}/execute` returns **405 Method Not Allowed** when `tool.backend == False`.

**Rationale**:
- 405 is semantically correct: the resource (tool) exists, but the HTTP method (POST) is not supported for it.
- 404 (Not Found) would be misleading — the tool exists, it's in `/tools`, it's in the admin panel.
- 501 (Not Implemented) is for server-wide unimplemented methods, not resource-specific restrictions.
- 403 (Forbidden) implies an auth/permission issue, which is incorrect.
- 200 with an empty body or `{success: false}` would be misleading — it implies the request was processed.

**Implementation**: The execute route handler (in `api_v1.py` or a shared guard) checks `tool.get_definition().backend` before dispatching to `tool.execute()`. If `backend` is `False`, it returns 405 immediately. The tool class never has its `execute()` method called for frontend-only tools.

**Response body** (405):
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

### 3.3 `execute()` Not Implemented Server-Side

**Decision**: Frontend-only tools do **not** override `execute()`. The base class `BaseTool.execute()` raises `NotImplementedError`, but the route handler's `backend: false` guard ensures it's never reached.

**Rationale**:
- A stub `execute()` that returns `ToolResult(success=False, error="not implemented")` would be dead code — the 405 guard makes it unreachable.
- Not overriding `execute()` is the clearest signal that this tool has no backend execution.
- If a developer accidentally bypasses the guard and calls `execute()`, the `NotImplementedError` is a loud, immediate failure (not a silent `success: false` that could be misinterpreted).

**Risk**: A future refactor that removes the `backend: false` guard from the route handler would cause 500 errors for frontend-only tools. Mitigation: the guard is implemented in a single, well-tested function (`check_tool_backend(tool)`) that is called in every tool execute route. A unit test verifies that frontend-only tools return 405.

### 3.4 Alternatives Rejected

| Alternative | Rationale for rejection |
|---|---|
| **Stub endpoint returning 200** | Misleading: implies successful execution. The frontend might display a "success" toast. |
| **Separate frontend-only registry** | Duplicates the tool lifecycle (seed, enable/disable, permissions, admin UI). Tools must be in the same registry to be manageable. |
| **Frontend-only config file** (e.g., `frontend_tools.json`) | No admin visibility. Admins couldn't disable the tool or restrict it by role. Bypasses the existing RBAC infrastructure. |
| **`execute()` returns `ToolResult(success=True, data=None)`** | Implies the tool "ran successfully with no output." An empty result is not the same as "this tool doesn't run here." |
| **Return 410 Gone** | 410 implies the endpoint existed but was removed. Not accurate — it was never implemented. |

## Consequences

### Positive
- **Minimal code change**: one field on `ToolDefinition`, one guard in the execute route handler, one new tool class file.
- **No migration**: `ToolModule` table is unchanged. The new tool is seeded on next boot like any other tool.
- **Admin works out of the box**: enable/disable toggle and role permission matrix function identically for frontend-only tools.
- **Discoverability**: `GET /tools` includes frontend-only tools with `"backend": false`. The frontend can render them without hardcoding.
- **Extensible**: future frontend-only tools (e.g., a Base64 encoder/decoder, a CIDR calculator) follow the exact same pattern — one new `SecretGeneratorTool`-style class, one `registry.register()` call.
- **Security**: no endpoint = no attack surface for SSRF, injection, or secret exfiltration via the backend. See `docs/security/review-secret-generator.md`.

### Negative
- **Non-standard HTTP semantics**: 405 with a JSON body is uncommon but valid (RFC 7231 does not prohibit a body on 405 responses).
- **`/tools` response grows**: each frontend-only tool adds ~500 bytes of parameter definitions to the `/tools` response. Acceptable for the current scale (< 10 tools).
- **Frontend must handle `backend: false`**: the tool page must not attempt a `POST .../execute` call. This is a one-line guard in the frontend tool dispatcher.

### Neutral
- The `backend` field is serialized in `to_api_definition()` but **not** persisted in `ToolModule` (which has no `backend` column). The source of truth is the Python `ToolDefinition`. If the field is changed in code, it takes effect on the next restart.

## References

- `functional-spec.md` §3.7 — Secret Generator functional requirements
- `spec-api-contract.md` §6 — `/tools` endpoint and `backend` field documentation
- `docs/specs/technical/spec-tool-secret-generator.md` — Technical specification
- `src/backend/app/tools/base.py` — `ToolDefinition` and `BaseTool` classes
- `src/backend/app/main.py:90-147` — Registry and seed pattern
