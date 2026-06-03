#!/usr/bin/env python3
"""Guard against docker-compose env-wiring regressions (issue #409).

The compose files inject the container environment via explicit
`environment:` blocks with `${VAR}` interpolation — there is no `env_file:`
directive, and no `.env` is baked into the image. So a setting that is NOT
listed in the backend service `environment:` block can never be configured
from `.env`: the value silently stays at its in-code default.

This was how `HEALTH_FULL_TOKEN` (broken `/health/full`) and
`WS_REQUIRE_ORIGIN` (CSWSH protection off in prod, ADR-009) slipped through.

This check fails CI if any security/ops-critical variable is missing from the
backend `environment:` block of the production-intent compose files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Production-intent compose files (dev compose is intentionally more permissive).
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")

# Must be wired into the backend `environment:` block. Keep in sync with the
# security/ops-critical settings in src/backend/app/config.py.
REQUIRED_BACKEND_ENV = {
    "SECRET_KEY",          # signing/encryption — must be overridable
    "ENVIRONMENT",         # gates prod validators
    "WS_REQUIRE_ORIGIN",   # CSWSH protection (ADR-009) — regression guard #409
    "HEALTH_FULL_TOKEN",   # /health/full enablement — regression guard #409
    "TRUSTED_PROXY_HOPS",  # client-IP trust (ADR-003)
    "CORS_ORIGINS",        # browser origin allowlist
}


def wired_backend_env(compose_path: Path) -> set[str]:
    """Return the set of env var names wired into the backend service."""
    data = yaml.safe_load(compose_path.read_text()) or {}
    backend = (data.get("services", {}) or {}).get("backend", {}) or {}
    env = backend.get("environment", []) or []
    if isinstance(env, dict):
        return set(env.keys())
    keys: set[str] = set()
    for item in env:
        if isinstance(item, str) and "=" in item:
            keys.add(item.split("=", 1)[0].strip())
    return keys


def main() -> int:
    failed = False
    for name in COMPOSE_FILES:
        path = REPO_ROOT / name
        if not path.exists():
            print(f"::error::{name} not found")
            failed = True
            continue
        missing = REQUIRED_BACKEND_ENV - wired_backend_env(path)
        if missing:
            failed = True
            print(
                f"::error file={name}::backend service is missing required env "
                f"wiring: {', '.join(sorted(missing))}"
            )
        else:
            print(f"{name}: OK")

    if failed:
        print(
            "\nFix: add the missing `- VARNAME=${VARNAME:-<default>}` lines to the "
            "backend service `environment:` block. See issue #409."
        )
        return 1
    print("\nAll required backend env vars are wired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
