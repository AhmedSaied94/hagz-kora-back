# Phase 9 — Production Hardening

**Duration:** Week 13–14
**Priority:** P1

**Goal:** Platform is secure, observable, performant, and meets the Definition of Done from the PRD.

---

## AI Execution Guide

| Task | Model | Effort | Notes |
|------|-------|--------|-------|
| Security audit (auth surfaces, rate limiting, input validation, admin IP whitelist) | `opus-4-6` | Extended thinking | Full adversarial review — model attacker paths across auth, booking, file upload, admin panel |
| ORM query audit (N+1 elimination, `select_related`/`prefetch_related`) | `sonnet-4-6` | High | Systematically review every list endpoint; use Django Debug Toolbar output as input |
| Coverage gap closure (bookings, tournaments, auth — target 80%+) | `sonnet-4-6` | High | Integration tests must hit real DB + Redis; write missing tests for critical paths first |
| Structured logging (`structlog`) + Sentry integration | `sonnet-4-6` | Medium | Wire `request_id` and `user_id` into every log line; verify Sentry DSN is env-var-only |
| PgBouncer + Gunicorn + Nginx config tuning | `sonnet-4-6` | Medium | Follow load test results; don't tune blind |
| Repetitive test writing for lower-priority modules (reviews, notifications) | `haiku-4-5` | Low | Pattern is established — use Haiku to fill coverage gaps in simpler modules |
| Celery monitoring (Flower), health check verification | `haiku-4-5` | Low | Config-level work |
| Infrastructure checklist items (DB snapshots, `.env.example` audit, Docker parity) | `haiku-4-5` | Low | Verification tasks, not implementation |

> **Lead with the security audit (Opus, extended thinking) before any other hardening task.** Vulnerabilities found late are expensive. After the audit, Sonnet handles the ORM and test coverage work in parallel with Haiku handling boilerplate verification tasks.

---

## Performance

| Task | Detail |
|------|--------|
| PgBouncer | Connection pooling in production — prevents DB connection exhaustion under load |
| Redis cache audit | Verify search result caching (60s TTL) is in place; add caching for stadium detail if needed |
| ORM query audit | `select_related`/`prefetch_related` on all FK/M2M traversals; eliminate N+1 queries via Django Debug Toolbar in staging |
| Celery worker tuning | Set concurrency based on load testing results |
| Pagination enforcement | Confirm all list endpoints are paginated (cursor-based, 20 items default) |

**Performance targets (from SRS):**
- Search API p95 < 300ms
- Booking confirmation p95 < 500ms
- Stadium detail p95 < 200ms

---

## Security

| Task | Detail |
|------|--------|
| IP whitelist admin endpoints | `/admin-panel/` accessible only from whitelisted IPs in production |
| HTTPS enforcement | HTTP → HTTPS redirect via Nginx; HSTS header |
| JWT short-lived tokens | 60 min access, 30 day refresh with blacklist |
| Rate limiting audit | OTP: 3 req/phone/15min; brute-force via `django-axes` |
| django-axes | Lock accounts after repeated failed login attempts |
| Upload validation | File type and size validated before S3 upload (JPEG/PNG/WebP, max 8MB) |
| Input sanitization | All user inputs validated server-side via DRF serializers |
| CSRF protection | Enabled for all web dashboard forms |
| Secret management audit | Confirm zero secrets in source code; all via env vars |

---

## Observability

| Task | Detail |
|------|--------|
| Structured logging | `structlog` with JSON output — log level, request ID, user ID on all log lines |
| Sentry | Error tracking + performance monitoring; DSN via env var |
| Health check | `GET /api/health/` returns 200 with DB + Redis connectivity status |
| Celery monitoring | Flower or Prometheus exporter for task queue visibility |

---

## Testing

**Coverage target: 80%+ for core modules**

| Module | Priority |
|--------|---------|
| `bookings` (booking engine + locking) | Critical |
| `tournaments` (fixture generation, standings) | Critical |
| `auth_users` (OTP flow, JWT, rate limiting) | Critical |
| `stadiums` (approval workflow, slot generation) | High |
| `reviews` (eligibility, aggregation) | Medium |

**Rules:**
- Integration tests hit a real PostgreSQL+PostGIS database — no mocking the DB
- Unit tests mock external services (FCM, SMS, S3)
- Test/staging uses `DJANGO_AUTH_BACKEND=email`

---

## Localization

| Task | Detail |
|------|--------|
| Bilingual fields | All user-facing text fields: `_ar` / `_en` variants |
| Timezone | Stored in UTC; displayed in `Africa/Cairo` (UTC+2) |
| RTL support | API returns separate language fields; Flutter client selects based on device locale |
| Arabic SMS content | All SMS messages composed in Arabic |

---

## Definition of Done (from PRD)

Before any feature is considered complete:

- [ ] Passing unit tests with coverage ≥ 80% for the module
- [ ] API endpoint documented in OpenAPI spec (`/api/schema/` via drf-spectacular)
- [ ] Arabic and English copy reviewed and approved
- [ ] Relevant push notification paths tested end-to-end
- [ ] Docker Compose (local) confirmed working after change
- [ ] Code reviewed and approved by at least one peer

---

## Infrastructure Checklist

- [ ] Daily automated PostgreSQL snapshot with 30-day retention
- [ ] Maintenance window documented: Fridays 02:00–04:00 Cairo time
- [ ] `.env.example` up to date with all required variables
- [ ] Docker images for DB, Redis, Celery, App are identical across local/staging/production
- [ ] Gunicorn worker count tuned
- [ ] Nginx config: HTTPS, gzip, static file serving, proxy headers
