# Phase 0 — Project Foundation & Infrastructure

**Duration:** Week 1–2  
**Priority:** P0 (launch blocker)

**Goal:** A running, containerized Django project that every future phase can build on.

---

## Tasks

| # | Task | Notes |
|---|------|-------|
| 0.1 | Django 5.x project scaffold | `django-admin startproject hagzkora` |
| 0.2 | App layout | `apps/` namespace: `auth_users`, `stadiums`, `bookings`, `tournaments`, `reviews`, `notifications`, `dashboards` |
| 0.3 | Docker Compose (local) | Services: `db` (PostgreSQL+PostGIS), `redis`, `celery_worker`, `celery_beat` |
| 0.4 | Docker Compose (prod) | Adds `app` (Gunicorn) + `nginx` |
| 0.5 | Settings split | `settings/base.py`, `settings/local.py`, `settings/production.py` via `python-decouple` |
| 0.6 | `.env.example` | All required env vars documented, no secrets in repo |
| 0.7 | Ruff linter + pre-commit | PEP 8 enforcement in CI |
| 0.8 | drf-spectacular | OpenAPI 3.0 schema auto-generation at `/api/schema/` |
| 0.9 | Base model | Abstract `TimeStampedModel` with `created_at`, `updated_at` |
| 0.10 | Health check endpoint | `GET /api/health/` — used by load balancer |
| 0.11 | CI skeleton | GitHub Actions: lint → test → build image |

---

## Deliverable

`docker compose -f docker-compose.local.yml up` starts all backing services.  
`python manage.py runserver` starts Django connected to them via localhost port mappings.

---

## Key Decisions

- **Custom User model must be defined before the first migration** — changing it later requires painful data migrations.
- Local dev: Django runs natively (fast iteration, debugger support). Only DB, Redis, Celery run in Docker.
- Production: all services including the app container run in Docker.
- No secrets ever committed — `.env.example` as reference, actual `.env` gitignored.
