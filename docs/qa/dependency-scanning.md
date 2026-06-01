# Dependency Vulnerability Scanning

## Overview

Automated vulnerability scanning runs in CI on every push to `master`, every pull request, and on a weekly schedule (Monday 07:23 UTC). Three tools cover the application's dependency trees.

See [ADR-010](../adr/adr-010-dependency-scanning.md) for the tool selection rationale.

## Tools and Thresholds

| Tool | Ecosystem | Failure Threshold | Advisory? |
|------|-----------|-------------------|-----------|
| `pip-audit` | Python (backend) | Any vulnerability | No — blocks CI |
| `npm audit` | JavaScript (frontend) | High and critical | No — blocks CI |

## Exception Policy

When a vulnerability is disclosed with no fix available, or when upgrading would require disproportionate effort, an exception may be granted.

### Process

1. **Open an issue** titled `CVE Exception: <CVE-ID> (<package>)` with:
   - CVE or PYSEC/GHSA identifier
   - Affected package and version
   - Impact assessment for SAKN's threat model
   - Why the fix cannot be applied immediately
   - **Expiry date** (maximum 90 days from filing)

2. **Add the ignore directive** to CI:

   Backend (`pip-audit`):
   ```yaml
   - run: pip-audit --desc on --ignore-vuln PYSEC-YYYY-NNNN
   ```

   Frontend (`npm audit`): add the GHSA id to the `ALLOWLIST` array in the
   `Run npm audit (with tracked exception allowlist)` step of
   `.github/workflows/dependency-scan.yml`. Each entry MUST include a
   comment with the package, justification, tracking issue, and expiry
   date. Example:

   ```yaml
   # GHSA-xxxx-xxxx-xxxx — <package> (<rationale>). Tracked in #NNN. Expires YYYY-MM-DD.
   ALLOWLIST=("GHSA-xxxx-xxxx-xxxx")
   ```

   The step uses `jq` to extract GHSA ids from `npm audit --json` and
   compares them against the allowlist. Any high/critical advisory not in
   the allowlist still fails the CI job.

3. **Document the exception** in the table below.

### Active Exceptions

| CVE / Advisory | Package | Filed | Expires | Issue | Rationale |
|----------------|---------|-------|---------|-------|-----------|
| GHSA-5xrq-8626-4rwp | vitest (`<4.1.0`) | 2026-06-01 | 2026-08-30 | #334 | devDep only — Vitest UI server not started by project scripts. SemVer-major upgrade (3 → 4) deferred to a dedicated PR. |

## Weekly Scan

The scheduled scan (`23 7 * * 1`) ensures newly-disclosed vulnerabilities are detected within a week, even on branches with no active development. Failures on the scheduled scan trigger the same exception process.

## First-Run Notes

The first CI run after enabling scanning may surface existing vulnerabilities in the current dependency tree. These should be triaged as follows:

1. **Critical/High with fix available**: Upgrade immediately in a dedicated PR.
2. **Critical/High without fix**: File an exception (see above) and plan the upgrade.
3. **Medium/Low**: File a backlog issue; does not require an exception (npm audit ignores these by default; pip-audit findings must be explicitly ignored if blocking).

## CI Workflow Reference

Workflow file: `.github/workflows/dependency-scan.yml`
