# Technical Specifications — SAKN MVP

> **Version:** 3.0
> **Status:** Draft
> **Date:** 2026-05-14

This directory contains the technical specifications split by concern. Load only the documents relevant to your task.

---

## Documents

| Document | Scope | Size |
|---|---|---|
| `spec-common.md` | Framework choices, tooling, identifiers, config, testing, risk register, open questions | ~185 lines |
| `spec-backend.md` | API design, data model, security, rate limiting, logging, Docker, module system | ~470 lines |
| `spec-frontend.md` | React component tree, state management, i18n, theming, WebSocket client, CSRF handling | ~170 lines |
| `spec-tools-live.md` | WebSocket protocol, Ping, Traceroute, subprocess sandboxing, privileges | ~200 lines |
| `spec-tools-instant.md` | HTTP tool execution, DNS Lookup, TLS/SSL Viewer | ~85 lines |
| `spec-api-contract.md` | Request/response schemas, pagination, error codes, message keys — the frontend/backend contract | ~345 lines |

---

## Which Documents to Load

| Task | Documents |
|---|---|
| **Initialize the project** | `spec-common.md` |
| **Implement backend auth (register, login, sessions)** | `spec-common.md` → `spec-backend.md` → `spec-api-contract.md` |
| **Implement backend API infrastructure (routing, middleware, DI)** | `spec-common.md` → `spec-backend.md` |
| **Implement data model & migrations** | `spec-common.md` → `spec-backend.md` |
| **Implement security filter & CSRF** | `spec-common.md` → `spec-backend.md` |
| **Implement rate limiting** | `spec-common.md` → `spec-backend.md` |
| **Implement Ping** | `spec-common.md` → `spec-backend.md` → `spec-tools-live.md` → `spec-api-contract.md` |
| **Implement Traceroute** | `spec-common.md` → `spec-backend.md` → `spec-tools-live.md` → `spec-api-contract.md` |
| **Implement DNS Lookup** | `spec-common.md` → `spec-backend.md` → `spec-tools-instant.md` → `spec-api-contract.md` |
| **Implement TLS/SSL Viewer** | `spec-common.md` → `spec-backend.md` → `spec-tools-instant.md` → `spec-api-contract.md` |
| **Implement admin interface (backend)** | `spec-common.md` → `spec-backend.md` → `spec-api-contract.md` |
| **Implement Docker deployment** | `spec-common.md` → `spec-backend.md` |
| **Build frontend app shell (routing, layout, providers)** | `spec-common.md` → `spec-frontend.md` |
| **Build frontend auth pages** | `spec-common.md` → `spec-frontend.md` → `spec-api-contract.md` |
| **Build frontend tool pages** | `spec-common.md` → `spec-frontend.md` → (`spec-tools-live.md` or `spec-tools-instant.md`) → `spec-api-contract.md` |
| **Build frontend admin pages** | `spec-common.md` → `spec-frontend.md` → `spec-api-contract.md` |
| **Write tests** | `spec-common.md` + whichever spec covers the code under test |
| **Add a new tool (post-MVP)** | `spec-common.md` → `spec-backend.md` (§9.5) → `spec-api-contract.md` |
| **Security audit** | `spec-common.md` → `spec-backend.md` |
| **Frontend/backend integration** | `spec-api-contract.md` + relevant tool specs |

---

## Relationships

```
spec-common.md          ← loaded first for every task
    │
    ├── spec-backend.md     ← server-side logic
    │       └── spec-api-contract.md   ← network boundary
    │
    ├── spec-frontend.md    ← client-side logic
    │       └── spec-api-contract.md   ← network boundary
    │
    ├── spec-tools-live.md      ← Ping & Traceroute (WebSocket)
    │       └── spec-api-contract.md
    │
    └── spec-tools-instant.md   ← DNS & TLS (HTTP)
            └── spec-api-contract.md
```

---

## Original Document

The original monolithic `technical-spec.md` (v2.0) has been split into these documents.
