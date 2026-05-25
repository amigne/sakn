# Playwright E2E Test Suite

**Date**: 2026-05-25

## Quick start (local)

```bash
cd src/frontend
npx playwright test                  # all browsers, headless
npx playwright test --headed         # with browser UI
npx playwright test -g "login"       # filter by test name
npx playwright test --project=chromium  # single browser
```

The dev server (`npm run dev`) is started automatically via `webServer` in
`playwright.config.ts`. If you already have it running, set
`reuseExistingServer: true` or let the config reuse it locally (default).

## What runs in CI

The `.github/workflows/e2e.yml` workflow triggers on every push to `master`
and every pull request. It runs chromium and firefox in parallel.

**Backend-dependent tests** (5 tests across `layout.spec.ts`,
`tool-execution.spec.ts`, `traceroute.spec.ts`) are skipped in CI with
`test.skip(!!process.env.CI)`. They require a running backend and will be
re-enabled once the full-stack CI setup is in place (follow-up issue TBD).

## Interpreting flakes

A test that sometimes passes and sometimes fails is a flake. Before marking
it as such:

1. Reproduce locally with `--headed --repeat-each=10`
2. Check if a timing issue: try increasing `expect.timeout` or adding
   `waitForSelector` before the assertion
3. Check if state leakage: run the single test in isolation with `-g`
4. If the root cause is unclear, open an issue with the trace ZIP attached
   (for CI failures) and the test name

### Marking a known flake

```typescript
test.fixme("test name", async ({ page }) => {
  // Known flake — see issue #XXX
});
```

- Use `test.fixme()` (not `test.skip()`) so the test still runs but is
  allowed to fail. Playwright reports it as "fixme" in CI and does not
  fail the build.
- Always reference the tracking issue in a comment.
- Never mark a test as fixme without investigation. Sync with the reviewer
  first.

## Marking a backend-dependent test

When a test needs the backend but CI doesn't provide it yet:

```typescript
test("test name", async ({ page }) => {
  test.skip(!!process.env.CI, "Backend required — follow-up issue TBD");
  // ...
});
```

This lets the test run locally (where you can spin up the backend manually)
but skips it in CI.

## Report artifacts

CI uploads the Playwright HTML report as a build artifact (7-day retention).
Download from the GitHub Actions run page → Artifacts → `playwright-report-<browser>`.

## Configuration

See `src/frontend/playwright.config.ts`. Key settings:

| Setting | CI | Local |
|---------|----|-------|
| Workers | 1 | All cores |
| Retries | 2 | 0 |
| Traces | retain-on-failure | off |
| forbidOnly | yes | no |
