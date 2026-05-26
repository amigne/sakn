# Contributing to SAKN

This document captures the non-obvious workflow rules. For architectural decisions, see `docs/adr/`. For full specs, see `docs/specs/`.

## Delivery process

Validate before implementing:

1. Functional specification
2. UI specification
3. Technical specification
4. Acceptance criteria
5. Implementation plan

Document major decisions in `docs/specs/`, `docs/adr/`, `docs/qa/`, `docs/security/` as appropriate.

## Code style

- Backend: `ruff check src/backend/` must pass. Use SQLAlchemy `.is_(True)` (not `== True`) on boolean columns.
- Frontend: `npx biome check src/frontend/` must pass. Prefer `data-testid` over translatable selectors in e2e tests.
- Every feature includes tests, or a written reason explaining why tests are not applicable.

## Backend tests

Run the **full** suite from `src/backend/` (CI does not run pytest):

```bash
cd src/backend
uv run pytest tests/ -q
```

Tests share session-scoped state (in-memory rate limiter, session-scoped SQLite engine). Running a single test in isolation can hide pollution from earlier tests. Always re-run the full suite before opening a PR that adds tests.

## Database migrations — Alembic

**Always generate revision IDs via Alembic, never hand-write them.**

```bash
cd src/backend
alembic revision -m "short description"
# or for model-driven changes:
alembic revision --autogenerate -m "short description"
```

Alembic produces a random 12-character hexadecimal ID (e.g. `d7091a29b949`). Keep it as-is.

**Forbidden patterns** — they look random but are not, and they collide with future auto-generated IDs:

- `5a1b2c3d4e56` (sequential hex `5a 1b 2c 3d 4e 56`)
- `f1a2b3c4d5e6` (sequential hex `f1 a2 b3 c4 d5 e6`)
- `aabbccddeeff`, `0123456789ab`, or any "obviously hand-typed" pattern
- Reusing a revision ID from another project or example

**This rule applies equally to AI coding agents.** If you are an LLM generating a migration, run `alembic revision` via the shell and use the returned ID. Do **not** invent a hex string that "looks random" — it almost certainly won't be.

If you discover a manually-composed ID after merge:

1. Open an issue documenting the bad ID
2. Fix it in a dedicated PR (rename file + update `revision:` + update any `down_revision` pointing to the old ID)
3. **Document the required `UPDATE alembic_version SET version_num='<new>' WHERE version_num='<old>'`** in the PR body — every environment (dev DBs, staging, prod) that has already applied the migration needs this update before the next `alembic upgrade head` will succeed

See `docs/specs/technical/spec-backend.md` §4.3 for full migration strategy.

## Pull requests

- Small, reviewable changes preferred. One issue per PR when feasible.
- Title: `<type>: <short summary> (#<issue>)` (types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`).
- Body: Summary / Files changed / Tests run / Tests failing / Known limitations / Security considerations / Recommendation.
- Close issues via `Closes #<n>` in the squash-merge commit body (GitHub auto-closes when this lands on the default branch).

## Security-sensitive changes

Do not modify files in these paths without explicit reviewer validation:

- `src/backend/app/security/`
- `src/backend/app/middleware/session.py`, `csrf.py`, `security_headers.py`
- `src/backend/alembic/versions/`
- `docs/security/`
- `docs/adr/` (especially ADR-007, ADR-009)

For new dependencies, justify in the PR body (existing alternative considered, security/maintenance posture of the new package).

## Reporting issues found during review

Any non-blocking observation made while reviewing a PR must become a tracked GitHub issue (not just a PR comment). Cross-link the originating PR/issue. Comments on closed PRs are invisible to future work — issues persist.
