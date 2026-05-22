# ADR-010: Automated Dependency Vulnerability Scanning

## Status

Accepted — 2026-05-22

## Context

The security audit of 2026-05-18 (L-7) identified the absence of automated software composition analysis (SCA) in CI as a gap. Without regular vulnerability scanning, known CVEs in third-party dependencies can remain undetected for extended periods. The project has two dependency trees — Python (backend, managed via `uv` / `pyproject.toml`) and JavaScript (frontend, managed via `npm` / `package.json`) — each requiring its own scanning tool.

The scan must integrate into CI with clear failure thresholds so that new vulnerabilities block PRs without creating excessive noise from low-severity or unfixable findings.

## Options Considered

### (a) pip-audit + npm audit + OSV-Scanner (multi-tool)

Use the native ecosystem tool for each language, plus an OS-level scanner for lockfile/OS package coverage.

- **pip-audit**: Audits installed Python packages against the PyPA vulnerability database (OSV-backed). No API key required. Fast (sub-10s for ~16 dependencies).
- **npm audit**: Built into npm, audits against the GitHub Advisory Database. `--audit-level=high` fails only on high/critical.
- **OSV-Scanner**: Google's open-source scanner, checks `uv.lock` and `package-lock.json` against the OSV database. Runs as advisory-only (`continue-on-error`).

**Pros:** Each tool is the standard for its ecosystem. No vendor lock-in. Zero cost (all are open-source / built-in). pip-audit is PyPA-backed.
**Cons:** Three tools to maintain in CI. Different output formats. OSV-Scanner may duplicate findings from pip-audit and npm audit.

### (b) Snyk

Single commercial tool covering both ecosystems plus Docker images.

**Pros:** Unified dashboard. Broad language support. Fix PRs for some vulnerabilities.
**Cons:** Requires API key and account. Free tier limited to 200 tests/month. Vendor lock-in for vulnerability database.

### (c) Safety (pyup.io)

Python-only commercial scanner.

**Pros:** Mature, well-known in Python ecosystem.
**Cons:** Requires API key for full database access. Free tier is rate-limited. Only covers Python — would still need a separate JS tool.

### (d) GitHub Dependabot

Built into GitHub, files dependency update PRs.

**Pros:** No CI configuration needed. Automatic fix PRs. Native GitHub integration.
**Cons:** Only files PRs — does not block merges by default. Limited to repository-level alerts, not CI gates. No unified policy across ecosystems.

## Decision

**Option (a): pip-audit + npm audit + OSV-Scanner (advisory).**

- **pip-audit**: Audits the installed virtual environment after `uv sync --frozen`. Fails the CI job on any vulnerability (default behavior).
- **npm audit**: Runs with `--audit-level=high`, failing only on high and critical severity findings.
- **OSV-Scanner**: Runs as an advisory check (`continue-on-error: true`) against all lockfiles in the repository. Findings are visible in CI logs but do not block merges.

**Triggers:**
- On push to `master`
- On every pull request
- Weekly scheduled scan (Monday 07:23 UTC) to catch newly-disclosed CVEs independently of code changes

**Failure policy:**
- Backend (`pip-audit`): fail on any vulnerability. If a CVE has no fix available, it can be temporarily ignored via `pip-audit --ignore-vuln PYSEC-YYYY-NNNN` with a documented expiry date in `docs/qa/dependency-scanning.md`.
- Frontend (`npm audit`): fail on high and critical. Medium and low are informational only.
- OSV-Scanner: advisory only. Does not block CI.

## Consequences

- **CI may break independently of code changes** when new CVEs are disclosed. The weekly scheduled scan provides early warning, and the exception policy in `docs/qa/dependency-scanning.md` defines the process for handling unfixable vulnerabilities.
- **New dependencies** added via PR will be scanned immediately, preventing vulnerable packages from entering the codebase.
- **A follow-up sprint** may be needed to address any existing CVEs discovered on the first scan. The exception policy allows accepting known vulnerabilities with a documented deadline for remediation.
- **pip-audit is not a project dependency** — it is installed in CI only, keeping the application dependency tree unchanged.
- **npm audit requires a `package-lock.json`** — `npm ci` generates this from `package.json`. If the team switches to a different lockfile format in the future, the CI step will need adjustment.
