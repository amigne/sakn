# ADR-006: RoleToolPermission Unique Constraint

## Status
Accepted — 2026-05-21

## Context
The `role_tool_permissions` table has no unique constraint on `(role, tool_id)`.
Two code paths insert rows with a non-atomic select-then-insert pattern:
- Seed code in `main.py` (lifespan startup)
- Self-healing in `tools.py:_check_tool_access()`

Under concurrent requests or app restarts, duplicate `(role, tool_id)` rows can
accumulate. The access checks use `scalar_one_or_none()` which silently returns
only the first row, masking the problem.

## Decision
Add `UniqueConstraint(role, tool_id)` on `role_tool_permissions` with a
pre-migration deduplication step.

**Dedup strategy**: Keep the row with the lowest `id` for each `(role, tool_id)`
group. Since `id` is a UUIDv7 (time-sortable), `MIN(id)` is the oldest row —
the one created by the initial seed, not a race-condition duplicate.

**Pre-migration**:
```sql
DELETE FROM role_tool_permissions
WHERE id NOT IN (
    SELECT MIN(id) FROM role_tool_permissions GROUP BY role, tool_id
);
```

**Migration**: Add `UNIQUE(role, tool_id)` plus a lookup index.

**Self-healing collision**: The `_check_tool_access()` auto-create now catches
`IntegrityError` (race between SELECT and INSERT) and re-queries for the row
that won the race.

## Consequences
- Duplicate `(role, tool_id)` rows are prevented at the database level.
- The seed code in `main.py` and self-healing code in `tools.py` retain their
  select-then-insert pattern — the unique constraint acts as a safety net.
- `IntegrityError` catch in the self-healing path adds minimal overhead (only
  triggers during races, which are rare).

## Rollback
Drop the unique constraint and index:
```sql
ALTER TABLE role_tool_permissions DROP CONSTRAINT uq_role_tool_permission_role_tool;
DROP INDEX ix_role_tool_permission_role_tool;
```
