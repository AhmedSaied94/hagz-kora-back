# Hagz Kora — Backend Implementation Docs

This directory contains the phase-by-phase backend implementation plan derived from the PRD and SRS.

## Documents

| File | Phase | Topic |
|------|-------|-------|
| [00_implementation_plan.md](00_implementation_plan.md) | Overview | Full phase summary, critical path, deferred features |
| [01_phase0_foundation.md](01_phase0_foundation.md) | Phase 0 | Project scaffold, Docker, settings, CI |
| [02_phase1_auth.md](02_phase1_auth.md) | Phase 1 | Auth (phone OTP / email), JWT, player & owner profiles |
| [03_phase2_stadium_management.md](03_phase2_stadium_management.md) | Phase 2 | Stadium CRUD, gallery (S3), slots, approval workflow |
| [04_phase3_search_discovery.md](04_phase3_search_discovery.md) | Phase 3 | PostGIS radius search, filters, stadium detail |
| [05_phase4_booking_engine.md](05_phase4_booking_engine.md) | Phase 4 | Redis-locked booking, states, cancellation |
| [06_phase5_notifications.md](06_phase5_notifications.md) | Phase 5 | FCM push, SMS service layer, device tokens |
| [07_phase6_tournament_engine.md](07_phase6_tournament_engine.md) | Phase 6 | Tournament creation, fixture generation (3 formats), standings |
| [08_phase7_ratings_reviews.md](08_phase7_ratings_reviews.md) | Phase 7 | Reviews gated to completed bookings, owner responses |
| [09_phase8_dashboards.md](09_phase8_dashboards.md) | Phase 8 | Owner & Admin dashboards (Django templates + React WCs) |
| [10_phase9_production_hardening.md](10_phase9_production_hardening.md) | Phase 9 | Performance, security, observability, Definition of Done |

## Source Documents

The original PRD and SRS are at the project root:
- `../../HAGZKORA_PRD.docx`
- `../../HAGZKORA_SRS.docx`

## Tech Stack

- **Django 5.x** + Django REST Framework
- **PostgreSQL 16** + PostGIS 3.x
- **Redis 7** — OTP storage, distributed booking locks, search cache
- **Celery 5** + Celery Beat — async tasks, scheduled slot generation
- **JWT** — `djangorestframework-simplejwt`
- **Firebase Cloud Messaging** — push notifications
- **SMS gateway** — Vonage or local Egyptian provider (abstracted via `services/notifications/sms.py`)
- **S3-compatible storage** — `django-storages`
- **Docker + Docker Compose** — identical environments across local/staging/production
