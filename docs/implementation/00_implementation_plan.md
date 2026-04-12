# Hagz Kora — Backend Implementation Plan

## Overview

**Stack:** Django 5.x + DRF · PostgreSQL 16 + PostGIS · Redis 7 · Celery 5 · JWT · FCM · S3 · Docker

**Guiding principles from PRD/SRS:**
- Stateless REST API consumed by Flutter, Owner Dashboard, Admin Dashboard
- Race-condition-safe booking via Redis distributed locking
- PostGIS for spatial stadium search
- Bilingual fields (`name_ar`, `name_en`) everywhere
- Phone OTP (production) / Email+Password (dev/staging) — toggled by `DJANGO_AUTH_BACKEND`

---

## Phase Summary

| Phase | Feature Area | Weeks | Priority |
|-------|-------------|-------|----------|
| 0 | Project Foundation & Docker | 1–2 | P0 |
| 1 | Auth & User Profiles | 2–3 | P0 |
| 2 | Stadium Management | 3–5 | P0 |
| 3 | Search & Discovery | 5–6 | P0 |
| 4 | Booking Engine | 6–8 | P0 |
| 5 | Notifications | 7–8 | P0 |
| 6 | Tournament Engine | 8–11 | P1 |
| 7 | Ratings & Reviews | 10–11 | P1 |
| 8 | Owner & Admin Dashboards | 11–13 | P1 |
| 9 | Production Hardening | 13–14 | P1 |

---

## AI Model Guide (per Phase)

Each phase document contains a detailed per-task breakdown. This table shows the leading model and the tasks that require Opus with extended thinking.

| Phase | Primary Model | Requires Opus + Extended Thinking |
|-------|--------------|-----------------------------------|
| 0 — Foundation | `haiku-4-5` / `sonnet-4-6` | No — Custom User model is Sonnet high-effort |
| 1 — Auth | `sonnet-4-6` | **Yes** — OTP security design, JWT strategy |
| 2 — Stadium Mgmt | `sonnet-4-6` | No — Idempotent slot gen is Sonnet high-effort |
| 3 — Search | `sonnet-4-6` | **Yes** — PostGIS query + Redis cache design |
| 4 — Booking Engine | `opus-4-6` | **Yes** — Redis lock design is the highest-risk task in the codebase |
| 5 — Notifications | `sonnet-4-6` / `haiku-4-5` | No — Well-specified service wiring |
| 6 — Tournament | `opus-4-6` | **Yes** — All three fixture algorithms + tiebreaker standings |
| 7 — Ratings | `sonnet-4-6` | No — Lightest phase; unique constraint is the only gotcha |
| 8 — Dashboards | `sonnet-4-6` | **Yes** — React WC + Django template integration architecture |
| 9 — Hardening | `sonnet-4-6` | **Yes** — Full adversarial security audit |

**Model key:**
- `haiku-4-5` — Boilerplate, formulaic CRUD, config tasks
- `sonnet-4-6` — Standard implementation, service wiring, complex views
- `opus-4-6` — Algorithm design, security-critical decisions, architectural trade-offs

**Effort levels** (defined per-task in each phase doc):
- **Low** — Formulaic, minimal judgment
- **Medium** — Standard implementation work
- **High** — Complex logic, multi-step reasoning
- **Extended thinking** — Enable with `Alt+T`; use for the hardest design decisions before any code is written

---

## Critical Path

```
Phase 0 → Phase 1 (Auth) → Phase 2 (Stadiums) → Phase 3 (Search)
                                                          ↓
                                              Phase 4 (Booking) ← Phase 5 (Notifications)
                                                          ↓
                                              Phase 6 (Tournaments) → Phase 7 (Reviews)
                                                          ↓
                                              Phase 8 (Dashboards) → Phase 9 (Hardening)
```

Phases 4 and 5 can be developed in parallel. Phase 7 depends on Phase 4 (completed bookings required for review eligibility).

---

## Deferred to Phase 2 (Post-Launch)

| Feature | Reason |
|---------|--------|
| Online payment (Fawry/instapay) | Requires payment provider integration & compliance |
| Recurring bookings | `RecurringBookingGroup` FK design noted in SRS for future |
| Next.js SPA dashboards | Deferred to avoid dual paradigm shift during MVP |
| Padel / basketball support | Explicitly out of scope in Phase 1 |
| Revenue analytics | No direct revenue mechanism in Phase 1 |
