# Playwright Trace Retention Policy

**Date**: 2026-05-21

## Trace mode

- **CI**: `retain-on-failure` — traces are saved only for failed tests
- **Local**: `off` — traces are disabled for performance and data safety

## Rationale

`on-first-retry` saves traces on the first retry regardless of whether the
test ultimately passes, which accumulates unnecessary trace data and can
capture sensitive information (cookies, session tokens, form input) in the
trace files. `retain-on-failure` only persists traces when a test fails,
which is when they are actually needed for debugging.

Traces contain a full recording of the page DOM, network requests, and
console output. They must never be committed to version control.

## Viewing traces

```bash
npx playwright show-trace test-results/<path>/trace.zip
```

Or open the HTML report and click the trace icon next to a failed test.

## Retention

- **CI**: Traces in `test-results/` are purged between runs by the CI
  runner's workspace cleanup. No manual action needed.
- **Local**: Delete `test-results/` manually when no longer needed:
  ```bash
  rm -rf test-results/
  ```

## Security

Trace files (`.zip`) contain page snapshots, network request/response data,
and JavaScript console output. Treat them as sensitive — do not share them
publicly or upload them to untrusted services.
